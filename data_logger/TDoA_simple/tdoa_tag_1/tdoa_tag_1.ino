#include "dw3000.h"

#define APP_NAME "MINIMAL TDOA TAG"

/* Minimal Config - Matches your working RX demo */
static dwt_config_t config = {
    5, DWT_PLEN_128, DWT_PAC8, 9, 9, 1, DWT_BR_6M8, 
    DWT_PHRMODE_STD, DWT_PHRRATE_STD, (129 + 8 - 8), 
    DWT_STS_MODE_OFF, DWT_STS_LEN_64, DWT_PDOA_M0
};

/* 
 * Frame Format:
 * [0] : 0xC5 (Blink type)
 * [1] : Sequence Number
 * [2-5] : Tag ID ('T','A','G','1')
 */
static uint8_t tx_msg[] = {0xC5, 0, 'T', 'A', 'G', '1'};

#define SN_IDX 1
#define FRAME_LENGTH (sizeof(tx_msg) + 2) // +2 for automatic CRC (FCS)
#define TX_DELAY_MS 10

extern dwt_txconfig_t txconfig_options;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println(APP_NAME);

  spiBegin();
  spiSelect();
  delay(200);

  /* Standard Initialization Sequence */
  while (!dwt_checkidlerc());
  dwt_softreset();
  delay(200);
  while (!dwt_checkidlerc());

  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) {
    Serial.println("INIT FAILED");
    while (1);
  }

  if (dwt_configure(&config)) {
    Serial.println("CONFIG FAILED");
    while (1);
  }

  dwt_configuretxrf(&txconfig_options);
}

void loop() {
  /* 1. Load the data into the chip */
  dwt_writetxdata(sizeof(tx_msg), tx_msg, 0);
  dwt_writetxfctrl(FRAME_LENGTH, 0, 0);

  /* 2. Start the radio transmitter */
  dwt_starttx(DWT_START_TX_IMMEDIATE);

  /* 3. Wait until the hardware says "Done" */
  while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS_BIT_MASK)) {
     // Wait for hardware flag
  }

  /* 4. Clear the hardware flag for the next time */
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);

  Serial.print("Blink Sent #");
  Serial.println(tx_msg[SN_IDX]);

  /* 5. Increment Sequence Number and Sleep */
  tx_msg[SN_IDX]++;
  delay(TX_DELAY_MS);
}