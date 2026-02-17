#include "dw3000.h"

/* 1. UNIQUE SETTINGS PER ANCHOR */
#define ANCHOR_NAME "A3"     // Change to "A2", "A3"
#define ANCHOR_ADDR_L 0x41   // 'A'
#define ANCHOR_ADDR_H 0x33   // '1' (Change to 0x32 for A2, 0x33 for A3)

/* COLLISION AVOIDANCE: 
   A1: 0ms, A2: 300ms, A3: 600ms. This prevents them from firing at the same time. */
#define START_DELAY_MS 0.01     // Change to 300 for A2, 600 for A3

#define TAG_ADDR_L 0x54      // 'T'
#define TAG_ADDR_H 0x31      // '1'

#define RNG_DELAY_MS 0.01    // Every anchor ranges once per second

/* ------------------------------------------------------------------------- */

static dwt_config_t config = {
    5, DWT_PLEN_128, DWT_PAC8, 9, 9, 1, DWT_BR_6M8, 
    DWT_PHRMODE_STD, DWT_PHRRATE_STD, (129 + 8 - 8), 
    DWT_STS_MODE_OFF, DWT_STS_LEN_64, DWT_PDOA_M0
};

#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

/* Frames updated with Addressing (Bytes 5-8) */
static uint8_t tx_poll_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, TAG_ADDR_L, TAG_ADDR_H, ANCHOR_ADDR_L, ANCHOR_ADDR_H, 0xE0, 0, 0};
static uint8_t rx_resp_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, ANCHOR_ADDR_L, ANCHOR_ADDR_H, TAG_ADDR_L, TAG_ADDR_H, 0xE1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

#define ALL_MSG_COMMON_LEN 10
#define RESP_MSG_POLL_RX_TS_IDX 10
#define RESP_MSG_RESP_TX_TS_IDX 14

static uint8_t frame_seq_nb = 0;
static uint8_t rx_buffer[20];
static uint32_t status_reg = 0;
extern dwt_txconfig_t txconfig_options;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.print(ANCHOR_NAME); Serial.println(" Starting...");

  spiBegin(); spiSelect(); delay(200);
  while (!dwt_checkidlerc());
  dwt_softreset(); delay(200);
  while (!dwt_checkidlerc());
  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) { while (1); }
  if (dwt_configure(&config)) { while (1); }
  
  dwt_configuretxrf(&txconfig_options);
  dwt_setrxantennadelay(RX_ANT_DLY);
  dwt_settxantennadelay(TX_ANT_DLY);
  
  dwt_setrxaftertxdelay(240);
  dwt_setrxtimeout(400);

  // Apply the start offset once to separate the anchors
  delay(START_DELAY_MS);
}

void loop() {
    /* 1. Send Poll to Specific Tag */
    tx_poll_msg[2] = frame_seq_nb;
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
    dwt_writetxdata(sizeof(tx_poll_msg), tx_poll_msg, 0);
    dwt_writetxfctrl(sizeof(tx_poll_msg), 0, 1);
    dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED);

    while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
    { };

    frame_seq_nb++;

    if (status_reg & SYS_STATUS_RXFCG_BIT_MASK) {
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);
        uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
        
        if (frame_len <= sizeof(rx_buffer)) {
            dwt_readrxdata(rx_buffer, frame_len, 0);
            
            /* Verify: Functional Code 0xE1 AND Destination is THIS Anchor */
            if (rx_buffer[9] == 0xE1 && rx_buffer[5] == ANCHOR_ADDR_L && rx_buffer[6] == ANCHOR_ADDR_H) {
                uint32_t poll_tx_ts, resp_rx_ts, poll_rx_ts, resp_tx_ts;
                int32_t rtd_init, rtd_resp;
                float clockOffsetRatio;

                poll_tx_ts = dwt_readtxtimestamplo32();
                resp_rx_ts = dwt_readrxtimestamplo32();
                clockOffsetRatio = ((float)dwt_readclockoffset()) / (uint32_t)(1<<26);

                resp_msg_get_ts(&rx_buffer[RESP_MSG_POLL_RX_TS_IDX], &poll_rx_ts);
                resp_msg_get_ts(&rx_buffer[RESP_MSG_RESP_TX_TS_IDX], &resp_tx_ts);

                rtd_init = resp_rx_ts - poll_tx_ts;
                rtd_resp = resp_tx_ts - poll_rx_ts;

                float tof = ((rtd_init - rtd_resp * (1 - clockOffsetRatio)) / 2.0) * DWT_TIME_UNITS;
                float distance = tof * 299792458.0;

                /* 2. PRINT JSON FOR THE PC */
                Serial.print("{\"anchor\":\"");
                Serial.print(ANCHOR_NAME);
                Serial.print("\", \"dist\":");
                Serial.print(distance, 3);
                Serial.println("}");
            }
        }
    } else {
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
    }

    delay(RNG_DELAY_MS);
}