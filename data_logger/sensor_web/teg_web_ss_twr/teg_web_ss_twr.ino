#include "dw3000.h"

#define APP_NAME "T1 SMART RESPONDER"

/* 1. TAG SETTINGS */
#define TAG_ADDR_L 0x54      // 'T'
#define TAG_ADDR_H 0x31      // '1'

static dwt_config_t config = {
    5, DWT_PLEN_128, DWT_PAC8, 9, 9, 1, DWT_BR_6M8, 
    DWT_PHRMODE_STD, DWT_PHRRATE_STD, (129 + 8 - 8), 
    DWT_STS_MODE_OFF, DWT_STS_LEN_64, DWT_PDOA_M0
};

#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

/* Frames updated for Addressing (Bytes 5-8) */
static uint8_t rx_poll_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, TAG_ADDR_L, TAG_ADDR_H, 0, 0, 0xE0, 0, 0};
static uint8_t tx_resp_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 0, 0, TAG_ADDR_L, TAG_ADDR_H, 0xE1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};

/* Indices for timestamps and addressing */
#define ALL_MSG_COMMON_LEN 10
#define POLL_MSG_SRC_ADDR_IDX 7   // Where the Anchor ID is in the Poll
#define RESP_MSG_DEST_ADDR_IDX 5  // Where to put Anchor ID in the Response
#define RESP_MSG_POLL_RX_TS_IDX 10
#define RESP_MSG_RESP_TX_TS_IDX 14

/* Fixed delay between Poll RX and Response TX */
#define POLL_RX_TO_RESP_TX_DLY_UUS 650

static uint64_t poll_rx_ts;
static uint64_t resp_tx_ts;
static uint8_t frame_seq_nb = 0;
static uint8_t rx_buffer[20];
static uint32_t status_reg = 0;
extern dwt_txconfig_t txconfig_options;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("Tag T1 Ready and Waiting...");

  spiBegin(); spiSelect(); delay(200);
  while (!dwt_checkidlerc());
  dwt_softreset(); delay(200);
  while (!dwt_checkidlerc());
  
  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) { while (1); }
  if (dwt_configure(&config)) { while (1); }
  
  dwt_configuretxrf(&txconfig_options);
  dwt_setrxantennadelay(RX_ANT_DLY);
  dwt_settxantennadelay(TX_ANT_DLY);
  
  dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE);
}

void loop() {
  /* 1. Activate reception immediately */
  dwt_rxenable(DWT_START_RX_IMMEDIATE);

  /* 2. Wait for reception or error */
  while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_ERR))) 
  { };

  if (status_reg & SYS_STATUS_RXFCG_BIT_MASK) {
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);
    uint32_t frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;

    if (frame_len <= sizeof(rx_buffer)) {
      dwt_readrxdata(rx_buffer, frame_len, 0);

      /* 3. Logic: Is it a Poll? (0xE0) AND is it meant for ME? (T1) */
      if (rx_buffer[9] == 0xE0 && rx_buffer[5] == TAG_ADDR_L && rx_buffer[6] == TAG_ADDR_H) {
        
        uint32_t resp_tx_time;
        int ret;

        /* A) Capture who sent this Poll (Anchor Address) */
        uint8_t anchor_addr_l = rx_buffer[7];
        uint8_t anchor_addr_h = rx_buffer[8];

        /* B) Retrieve RX timestamp */
        poll_rx_ts = get_rx_timestamp_u64();

        /* C) Set up Response (Put Anchor ID as Destination) */
        tx_resp_msg[RESP_MSG_DEST_ADDR_IDX] = anchor_addr_l;
        tx_resp_msg[RESP_MSG_DEST_ADDR_IDX + 1] = anchor_addr_h;
        tx_resp_msg[2] = rx_buffer[2]; // Use same sequence number as Poll

        /* D) Calculate exact time to send Response */
        resp_tx_time = (poll_rx_ts + (POLL_RX_TO_RESP_TX_DLY_UUS * UUS_TO_DWT_TIME)) >> 8;
        dwt_setdelayedtrxtime(resp_tx_time);
        resp_tx_ts = (((uint64_t)(resp_tx_time & 0xFFFFFFFEUL)) << 8) + TX_ANT_DLY;

        /* E) Write local timestamps into the message */
        resp_msg_set_ts(&tx_resp_msg[RESP_MSG_POLL_RX_TS_IDX], poll_rx_ts);
        resp_msg_set_ts(&tx_resp_msg[RESP_MSG_RESP_TX_TS_IDX], resp_tx_ts);

        /* F) Write data and send */
        dwt_writetxdata(sizeof(tx_resp_msg), tx_resp_msg, 0);
        dwt_writetxfctrl(sizeof(tx_resp_msg), 0, 1);
        ret = dwt_starttx(DWT_START_TX_DELAYED);

        if (ret == DWT_SUCCESS) {
          /* Wait for TX to finish before starting next RX */
          while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS_BIT_MASK));
          dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
          
          Serial.print("Replied to Anchor: "); 
          Serial.print((char)anchor_addr_l); Serial.println((char)anchor_addr_h);
        }
      }
    }
  } else {
    /* Clear RX error events */
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_ERR);
  }
}