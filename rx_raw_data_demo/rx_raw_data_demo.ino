#include "dw3000.h"

#define APP_NAME "RX RAW DATA DEMO"

// --- Basic UWB config (same as examples) ---
static dwt_config_t config = {
    5,               // Channel
    DWT_PLEN_128,    // Preamble length
    DWT_PAC8,        // PAC size
    9,               // TX preamble code
    9,               // RX preamble code
    1,               // SFD type
    DWT_BR_6M8,      // Data rate
    DWT_PHRMODE_STD, // PHY header mode
    DWT_PHRRATE_STD, // PHY header rate
    (129 + 8 - 8),   // SFD timeout
    DWT_STS_MODE_OFF,
    DWT_STS_LEN_64,
    DWT_PDOA_M0
};

// Antenna delays (same as Qorvo examples)
#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

// RX buffer
#define RX_BUF_LEN 127
static uint8_t rx_buffer[RX_BUF_LEN];

// CIR buffer: just grab first 128 bytes as a demo
#define CIR_BUF_LEN 128
static uint8_t cir_buf[CIR_BUF_LEN];

// Diagnostics struct from DW3000 API
static dwt_rxdiag_t rx_diag;

// For status flags
static uint32_t status_reg = 0;

// From library (TX power etc.)
extern dwt_txconfig_t txconfig_options;

// Print bytes as hex
static void print_bytes_hex(const uint8_t *buf, uint16_t len)
{
    for (uint16_t i = 0; i < len; i++) {
        if (buf[i] < 0x10) Serial.print('0');
        Serial.print(buf[i], HEX);
        Serial.print(' ');
    }
    Serial.println();
}

void setup()
{
    Serial.begin(115200);
    delay(1000);
    Serial.println();
    Serial.println(APP_NAME);

    // Start SPI + DW3000
    spiBegin();
    spiSelect();
    delay(200);

    while (!dwt_checkidlerc()) {
        Serial.println("IDLE FAILED");
    }

    dwt_softreset();
    delay(200);

    while (!dwt_checkidlerc()) {
        Serial.println("IDLE FAILED (after reset)");
    }

    if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) {
        Serial.println("INIT FAILED");
        while (1);
    }

    if (dwt_configure(&config)) {
        Serial.println("CONFIG FAILED");
        while (1);
    }

    dwt_configuretxrf(&txconfig_options);

    dwt_setrxantennadelay(RX_ANT_DLY);
    dwt_settxantennadelay(TX_ANT_DLY);

    // Enable LNA/PA
    dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE);

    // Enable CIA diagnostics so dwt_readdiagnostics() gives full data
    // (1 = log full diagnostic set, see DW3xxx API Guide)
    dwt_configciadiag(1);

    Serial.println("Ready, waiting for RX frames...");
}

void loop()
{
    // --- Put DW3000 into RX mode immediately ---
    dwt_rxenable(DWT_START_RX_IMMEDIATE);

    // Wait for good frame or RX error
    while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) &
             (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_ERR))) {
        // busy wait
    }

    if (status_reg & SYS_STATUS_RXFCG_BIT_MASK) {
        // ----- 1) STATUS / FLAGS -----
        Serial.println();
        Serial.println("=== RX FRAME ===");
        Serial.print("SYS_STATUS (low 32b): 0x");
        Serial.println(status_reg, HEX);

        // Clear good RX flag
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);

        // ----- 2) FRAME BUFFER -----
        uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
        if (frame_len > RX_BUF_LEN) frame_len = RX_BUF_LEN;

        dwt_readrxdata(rx_buffer, frame_len, 0);

        Serial.print("Frame length: ");
        Serial.println(frame_len);

        Serial.print("Frame bytes: ");
        print_bytes_hex(rx_buffer, frame_len);

        // ----- 3) RX TIMESTAMP -----
        uint64_t rx_ts = get_rx_timestamp_u64();
        Serial.print("RX timestamp (ticks): ");
        Serial.println((unsigned long)(rx_ts & 0xFFFFFFFFUL));  // low 32 bits
        Serial.print("RX timestamp (full 40b, hex): 0x");
        Serial.println((unsigned long)(rx_ts & 0xFFFFFFFFUL), HEX);

        // ----- 4) CIR ACCUMULATOR (first bytes) -----
        dwt_readaccdata(cir_buf, CIR_BUF_LEN, 0); // read from accumulator mem

        Serial.print("CIR first ");
        Serial.print(CIR_BUF_LEN);
        Serial.println(" bytes:");
        print_bytes_hex(cir_buf, CIR_BUF_LEN);

        // ----- 5) RX DIAGNOSTICS / QUALITY -----
        dwt_readdiagnostics(&rx_diag);

        Serial.print("ipatovPeak:   ");
        Serial.println(rx_diag.ipatovPeak);
        Serial.print("ipatovPower:  ");
        Serial.println(rx_diag.ipatovPower);
        Serial.print("ipatovFpIndex:");
        Serial.println(rx_diag.ipatovFpIndex);
        Serial.print("stsPeak:      ");
        Serial.println(rx_diag.stsPeak);
        Serial.print("stsPower:     ");
        Serial.println(rx_diag.stsPower);
        Serial.print("stsFpIndex:   ");
        Serial.println(rx_diag.stsFpIndex);
        Serial.print("xtalOffset:   ");
        Serial.println(rx_diag.xtalOffset);

        Serial.println("=== END FRAME ===");

    } else {
        // RX error → clear flags and try again
        Serial.println("RX ERROR");
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_ERR);
    }

    delay(100); // small pause between RX cycles
}
