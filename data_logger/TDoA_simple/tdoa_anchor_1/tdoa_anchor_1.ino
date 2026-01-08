#include "dw3000.h"

#define APP_NAME "TDOA ANCHOR v1.0"

/* CHANGE THIS FOR EACH ANCHOR: "A1", "A2", "A3" */
#define ANCHOR_ID "A1"

/* Default configuration - MUST match the Tag's config */
static dwt_config_t config = {
    5, DWT_PLEN_128, DWT_PAC8, 9, 9, 1, DWT_BR_6M8, 
    DWT_PHRMODE_STD, DWT_PHRRATE_STD, (129 + 8 - 8), 
    DWT_STS_MODE_OFF, DWT_STS_LEN_64, DWT_PDOA_M0
};

/* Buffer to store the incoming Blink message */
#define RX_BUF_LEN 24
static uint8_t rx_buffer[RX_BUF_LEN];

/* Status register and timestamp variables */
static uint32_t status_reg = 0;
static uint64_t rx_timestamp;

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);

  spiBegin();
  spiSelect();
  delay(200);

  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) {
    while (1);
  }

  if (dwt_configure(&config)) {
    while (1);
  }

  /* Set antenna delay. 
   * In TDOA, these must be calibrated carefully later for high accuracy. */
  dwt_setrxantennadelay(16385);
  
  /* Enable LEDs to see when a packet arrives */
  dwt_setleds(DWT_LEDS_ENABLE | DWT_LEDS_INIT_BLINK);
}

void loop() {
  /* 1. Clear status and turn on Receiver */
  dwt_write32bitreg(SYS_STATUS_ID, 0xFFFFFFFF);
  dwt_rxenable(DWT_START_RX_IMMEDIATE);

  /* 2. Wait for a message or error */
  while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_ERR))) { };

  if (status_reg & SYS_STATUS_RXFCG_BIT_MASK) {
    rx_timestamp = get_rx_timestamp_u64();
    uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
    
    if (frame_len <= RX_BUF_LEN) {
      dwt_readrxdata(rx_buffer, frame_len, 0);

      /* 
       * TAG DATA MAP:
       * rx_buffer[0] = 0xC5
       * rx_buffer[1] = Sequence Number
       * rx_buffer[2,3,4,5] = 'T','A','G','1'
       */
      
      uint8_t seq_num = rx_buffer[1]; // CORRECTED INDEX
      char tag_id[5];
      memcpy(tag_id, &rx_buffer[2], 4); // CORRECTED INDEX (starts at 2)
      tag_id[4] = '\0'; // Null terminator for string

      /* Clean JSON output */
      Serial.print("{\"anchor\":\"");
      Serial.print(ANCHOR_ID);
      Serial.print("\", \"tag\":\"");
      Serial.print(tag_id);
      Serial.print("\", \"seq\":");
      Serial.print(seq_num);
      Serial.print(", \"ts\":\"");
      /* Hex format for the 40-bit timestamp */
      Serial.print((uint32_t)(rx_timestamp >> 32), HEX); 
      Serial.print((uint32_t)(rx_timestamp & 0xFFFFFFFF), HEX);
      Serial.println("\"}");
    }
    /* Clear the RX flag */
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);
  } else {
    /* Clear error flags */
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_ERR);
  }
}