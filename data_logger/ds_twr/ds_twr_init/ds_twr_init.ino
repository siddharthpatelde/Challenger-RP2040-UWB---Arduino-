#include "dw3000.h"

#define APP_NAME "DS TWR INIT v1.0"

/* Default communication configuration. We use default non-STS DW mode. */
static dwt_config_t config = {
        5,               /* Channel number. */
        DWT_PLEN_128,    /* Preamble length. Used in TX only. */
        DWT_PAC8,        /* Preamble acquisition chunk size. Used in RX only. */
        9,               /* TX preamble code. Used in TX only. */
        9,               /* RX preamble code. Used in RX only. */
        1,               /* 0 to use standard 8 symbol SFD, 1 to use non-standard 8 symbol, 2 for non-standard 16 symbol SFD and 3 for 4z 8 symbol SDF type */
        DWT_BR_6M8,      /* Data rate. */
        DWT_PHRMODE_STD, /* PHY header mode. */
        DWT_PHRRATE_STD, /* PHY header rate. */
        (129 + 8 - 8),   /* SFD timeout (preamble length + 1 + SFD length - PAC size). Used in RX only. */
        DWT_STS_MODE_OFF, /* STS disabled */
        DWT_STS_LEN_64,/* STS length see allowed values in Enum dwt_sts_lengths_e */
        DWT_PDOA_M0      /* PDOA mode off */
};

/* Inter-ranging delay period, in milliseconds. */
//#define RNG_DELAY_MS 10003

/* Default antenna delay values for 64 MHz PRF. See NOTE 2 below. */
#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

/* Frames used in the ranging process. See NOTE 3 below. */
static uint8_t tx_poll_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'W', 'A', 'V', 'E', 0xE0, 0, 0};
static uint8_t rx_resp_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'V', 'E', 'W', 'A', 0xE1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};




//final message for T_reply2
static uint8_t tx_final_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'W', 'A', 'V', 'E', 0xE2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};
/* New indexes for the Final message timestamps */
#define FINAL_MSG_T_ROUND_1_IDX 10
#define FINAL_MSG_T_REPLY_2_IDX 14
/* Delay between Response RX and Final TX, in UWB microseconds. */
#define RESP_RX_TO_FINAL_TX_DLY_UUS 500




/* Length of the common part of the message (up to and including the function code, see NOTE 3 below). */
#define ALL_MSG_COMMON_LEN 10
/* Indexes to access some of the fields in the frames defined above. */
#define ALL_MSG_SN_IDX 2
#define RESP_MSG_POLL_RX_TS_IDX 10
#define RESP_MSG_RESP_TX_TS_IDX 14
#define RESP_MSG_TS_LEN 4
/* Frame sequence number, incremented after each transmission. */
static uint8_t frame_seq_nb = 0;

/* Buffer to store received response message.
 * Its size is adjusted to longest frame that this example code is supposed to handle. */
#define RX_BUF_LEN 20
static uint8_t rx_buffer[RX_BUF_LEN];

/* Hold copy of status register state here for reference so that it can be examined at a debug breakpoint. */
static uint32_t status_reg = 0;

/* Delay between frames, in UWB microseconds. See NOTE 1 below. */
#ifdef RPI_BUILD
#define POLL_TX_TO_RESP_RX_DLY_UUS 240
#endif //RPI_BUILD
#ifdef STM32F429xx
#define POLL_TX_TO_RESP_RX_DLY_UUS 240
#endif //STM32F429xx
#ifdef NRF52840_XXAA
#define POLL_TX_TO_RESP_RX_DLY_UUS 240
#endif //NRF52840_XXAA
/* Receive response timeout. See NOTE 5 below. */
#ifdef RPI_BUILD
#define RESP_RX_TIMEOUT_UUS 270
#endif //RPI_BUILD
#ifdef STM32F429xx
#define RESP_RX_TIMEOUT_UUS 210
#endif //STM32F429xx
#ifdef NRF52840_XXAA
#define RESP_RX_TIMEOUT_UUS 400
#endif //NRF52840_XXAA

#define POLL_TX_TO_RESP_RX_DLY_UUS 240
#define RESP_RX_TIMEOUT_UUS 400



/* Values for the PG_DELAY and TX_POWER registers reflect the bandwidth and power of the spectrum at the current
 * temperature. These values can be calibrated prior to taking reference measurements. See NOTE 2 below. */
extern dwt_txconfig_t txconfig_options;

void setup() {
  while (!Serial)
    delay(100);

  Serial.begin(115200);
  Serial.println(APP_NAME);

  /* Start SPI and get stuff going*/
  spiBegin();
  spiSelect();

  delay(200); // Time needed for DW3000 to start up (transition from INIT_RC to IDLE_RC, or could wait for SPIRDY event)

  while (!dwt_checkidlerc()) // Need to make sure DW IC is in IDLE_RC before proceeding 
  {
    Serial.print("IDLE FAILED\r\n");
    while (1);
  }

  dwt_softreset();
  delay(200);

  while (!dwt_checkidlerc()) // Need to make sure DW IC is in IDLE_RC before proceeding 
  {
    Serial.print("IDLE FAILED\r\n");
    while (1);
  }

  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR)
  {
    Serial.print("INIT FAILED\r\n");
    while (1);
  }

  /* Configure DW IC. See NOTE 6 below. */
  if(dwt_configure(&config)) // if the dwt_configure returns DWT_ERROR either the PLL or RX calibration has failed the host should reset the device
  {
    Serial.print("CONFIG FAILED\r\n");
    while (1);
  }

    /* Configure the TX spectrum parameters (power, PG delay and PG count) */
    dwt_configuretxrf(&txconfig_options);

    /* Apply default antenna delay value. See NOTE 2 below. */
    dwt_setrxantennadelay(RX_ANT_DLY);
    dwt_settxantennadelay(TX_ANT_DLY);

    /* Set expected response's delay and timeout. See NOTE 1 and 5 below.
     * As this example only handles one incoming frame with always the same delay and timeout, those values can be set here once for all. */
    dwt_setrxaftertxdelay(POLL_TX_TO_RESP_RX_DLY_UUS);
    dwt_setrxtimeout(RESP_RX_TIMEOUT_UUS);

    /* Next can enable TX/RX states output on GPIOs 5 and 6 to help debug, and also TX/RX LEDs
     * Note, in real low power applications the LEDs should not be used. */
    dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE);
}

void loop() {


        /* Write frame data to DW IC and prepare transmission. See NOTE 7 below. */
        tx_poll_msg[ALL_MSG_SN_IDX] = frame_seq_nb;
        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
        dwt_writetxdata(sizeof(tx_poll_msg), tx_poll_msg, 0); /* Zero offset in TX buffer. */
        dwt_writetxfctrl(sizeof(tx_poll_msg), 0, 1); /* Zero offset in TX buffer, ranging. */

        /* Start transmission, indicating that a response is expected so that reception is enabled automatically after the frame is sent and the delay
         * set by dwt_setrxaftertxdelay() has elapsed. */
        dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED);

        /* We assume that the transmission is achieved correctly, poll for reception of a frame or error/timeout. See NOTE 8 below. */
        while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
        { };

        /* Increment frame sequence number after transmission of the poll message (modulo 256). */
        frame_seq_nb++;

        if (status_reg & SYS_STATUS_RXFCG_BIT_MASK)
        {
            uint32_t frame_len;

            /* Clear good RX frame event in the DW IC status register. */
            dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);

            /* A frame has been received, read it into the local buffer. */
            frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
            if (frame_len <= sizeof(rx_buffer))
            {
                dwt_readrxdata(rx_buffer, frame_len, 0);

                /* Check that the frame is the expected response from the companion "SS TWR responder" example.
                 * As the sequence number field of the frame is not relevant, it is cleared to simplify the validation of the frame. */
                rx_buffer[ALL_MSG_SN_IDX] = 0;





              if (memcmp(rx_buffer, rx_resp_msg, ALL_MSG_COMMON_LEN) == 0)
                {
                    uint32_t poll_tx_ts, resp_rx_ts, final_tx_time;
                    uint64_t final_tx_ts;
                    uint32_t t_round1, t_reply2;

                    /* 1. Retrieve the timestamps for T_round1 */
                    poll_tx_ts = dwt_readtxtimestamplo32();
                    resp_rx_ts = dwt_readrxtimestamplo32();
                    t_round1 = resp_rx_ts - poll_tx_ts;

                    /* 2. Schedule the Final message to be sent at a fixed delay after Response RX */
                    /* This fixed delay is our T_reply2 */
                    final_tx_time = (resp_rx_ts + (RESP_RX_TO_FINAL_TX_DLY_UUS * UUS_TO_DWT_TIME)) >> 8;
                    dwt_setdelayedtrxtime(final_tx_time);

                    /* 3. Calculate the actual final TX timestamp (including antenna delay) */
                    /* Note: the DW3000 uses the 9th bit for sub-tick info, so we shift and add delay */
                    final_tx_ts = (((uint64_t)(final_tx_time & 0xFFFFFFFEUL)) << 8) + TX_ANT_DLY;
                    t_reply2 = (uint32_t)(final_tx_ts - resp_rx_ts);

                    /* 4. Pack T_round1 and T_reply2 into the Final message buffer */
                    resp_msg_set_ts(&tx_final_msg[FINAL_MSG_T_ROUND_1_IDX], t_round1);
                    resp_msg_set_ts(&tx_final_msg[FINAL_MSG_T_REPLY_2_IDX], t_reply2);

                    /* 5. Send the Final message */
                    tx_final_msg[ALL_MSG_SN_IDX] = frame_seq_nb;
                    dwt_writetxdata(sizeof(tx_final_msg), tx_final_msg, 0);
                    dwt_writetxfctrl(sizeof(tx_final_msg), 0, 1);
                    
                    if (dwt_starttx(DWT_START_TX_DELAYED) == DWT_SUCCESS)
                    {
                        /* Wait for TX to finish */
                        while (!(dwt_read32bitreg(SYS_STATUS_ID) & SYS_STATUS_TXFRS_BIT_MASK));
                        dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
                        
                        Serial.println("Final Sent - Data sent to Responder");
                    }
                  
                }




            }
        }
        else
        {
            /* Clear RX error/timeout events in the DW IC status register. */
            dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
        }

        

        /* Execute a delay between ranging exchanges. */
       // Sleep(RNG_DELAY_MS);
}