#include "dw3000.h"

#define APP_NAME "DS TWR RESP v1.0"

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

/* Default antenna delay values for 64 MHz PRF. See NOTE 2 below. */
#define TX_ANT_DLY 16385
#define RX_ANT_DLY 16385

/* Frames used in the ranging process. See NOTE 3 below. */
static uint8_t rx_poll_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'W', 'A', 'V', 'E', 0xE0, 0, 0};
static uint8_t tx_resp_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'V', 'E', 'W', 'A', 0xE1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0};






/* Message type for the Final message (Initiator uses 0xE2) */
static uint8_t rx_final_msg[] = {0x41, 0x88, 0, 0xCA, 0xDE, 'W', 'A', 'V', 'E', 0xE2, 0, 0};
/* Indices to extract T_round1 and T_reply2 from the Final message */
#define FINAL_MSG_T_ROUND_1_IDX 10
#define FINAL_MSG_T_REPLY_2_IDX 14
/* Timeout for the Final message (longer than Response to be safe) */
#define FINAL_RX_TIMEOUT_UUS 1000
/* Hold copies of computed time of flight and distance here for reference so that it can be examined at a debug breakpoint. */
static double tof;
static double distance;




/* Length of the common part of the message (up to and including the function code, see NOTE 3 below). */
#define ALL_MSG_COMMON_LEN 10
/* Index to access some of the fields in the frames involved in the process. */
#define ALL_MSG_SN_IDX 2
#define RESP_MSG_POLL_RX_TS_IDX 10
#define RESP_MSG_RESP_TX_TS_IDX 14
#define RESP_MSG_TS_LEN 4
/* Frame sequence number, incremented after each transmission. */
static uint8_t frame_seq_nb = 0;

/* Buffer to store received messages.
 * Its size is adjusted to longest frame that this example code is supposed to handle. */
#define RX_BUF_LEN 24//Must be less than FRAME_LEN_MAX_EX
static uint8_t rx_buffer[RX_BUF_LEN];

/* Hold copy of status register state here for reference so that it can be examined at a debug breakpoint. */
static uint32_t status_reg = 0;

/* Delay between frames, in UWB microseconds. See NOTE 1 below. */
#ifdef RPI_BUILD
#define POLL_RX_TO_RESP_TX_DLY_UUS 550
#endif //RPI_BUILD
#ifdef STM32F429xx
#define POLL_RX_TO_RESP_TX_DLY_UUS 450
#endif //STM32F429xx
#ifdef NRF52840_XXAA
#define POLL_RX_TO_RESP_TX_DLY_UUS 650
#endif //NRF52840_XXAA

#define POLL_RX_TO_RESP_TX_DLY_UUS 450

/* Timestamps of frames transmission/reception. */
static uint64_t poll_rx_ts;
static uint64_t resp_tx_ts;

/* Values for the PG_DELAY and TX_POWER registers reflect the bandwidth and power of the spectrum at the current
 * temperature. These values can be calibrated prior to taking reference measurements. See NOTE 5 below. */
extern dwt_txconfig_t txconfig_options;

void setup() {
//  while (!Serial)
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
    while (1) ;
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
    while (1) ;
  }

  // Enabling LEDs here for debug so that for each TX the D1 LED will flash on DW3000 red eval-shield boards.
  dwt_setleds(DWT_LEDS_ENABLE | DWT_LEDS_INIT_BLINK);

  /* Configure DW IC. See NOTE 6 below. */
  if(dwt_configure(&config)) // if the dwt_configure returns DWT_ERROR either the PLL or RX calibration has failed the host should reset the device
  {
    Serial.print("CONFIG FAILED\r\n");
    while (1) ;
  }

    /* Configure the TX spectrum parameters (power, PG delay and PG count) */
    dwt_configuretxrf(&txconfig_options);

    /* Apply default antenna delay value. See NOTE 2 below. */
    dwt_setrxantennadelay(RX_ANT_DLY);
    dwt_settxantennadelay(TX_ANT_DLY);

    /* Next can enable TX/RX states output on GPIOs 5 and 6 to help debug, and also TX/RX LEDs
     * Note, in real low power applications the LEDs should not be used. */
    dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE); 
}

void loop() {



        /* Activate reception immediately. */
        dwt_rxenable(DWT_START_RX_IMMEDIATE);

        /* Instead of just waiting for RXFCG, also wait for the internal math (CIA) to finish */
        while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_ERR)))
        { };

        /* Add a 10 microsecond 'breath' for the chip to finalize its internal registers */
        delayMicroseconds(10); 

        /* Now clear the flags */
        dwt_write32bitreg(SYS_STATUS_ID, 0xFFFFFFFF);

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

                /* Check that the frame is a poll sent by "SS TWR initiator" example.
                 * As the sequence number field of the frame is not relevant, it is cleared to simplify the validation of the frame. */
                rx_buffer[ALL_MSG_SN_IDX] = 0;
                if (memcmp(rx_buffer, rx_poll_msg, ALL_MSG_COMMON_LEN) == 0)
                {
                    uint32_t resp_tx_time;
                    int ret;

                    /* 1. Retrieve poll reception timestamp (RX) */
                    poll_rx_ts = get_rx_timestamp_u64();

                    /* 2. Compute and schedule response transmission (TX) */
                    resp_tx_time = (poll_rx_ts + (POLL_RX_TO_RESP_TX_DLY_UUS * UUS_TO_DWT_TIME)) >> 8;
                    dwt_setdelayedtrxtime(resp_tx_time);

                    /* Response TX timestamp is programmed time + antenna delay */
                    resp_tx_ts = (((uint64_t)(resp_tx_time & 0xFFFFFFFEUL)) << 8) + TX_ANT_DLY;

                    /* Prepare and send the response message */
                    resp_msg_set_ts(&tx_resp_msg[RESP_MSG_POLL_RX_TS_IDX], poll_rx_ts);
                    resp_msg_set_ts(&tx_resp_msg[RESP_MSG_RESP_TX_TS_IDX], resp_tx_ts);
                    tx_resp_msg[ALL_MSG_SN_IDX] = frame_seq_nb;
                    
                    dwt_writetxdata(sizeof(tx_resp_msg), tx_resp_msg, 0);
                    dwt_writetxfctrl(sizeof(tx_resp_msg), 0, 1);
                    
                    /* Start TX and tell chip to immediately turn on Receiver for the Final message */
                    dwt_setrxtimeout(FINAL_RX_TIMEOUT_UUS); // Set timeout for the Final message
                    ret = dwt_starttx(DWT_START_TX_DELAYED | DWT_RESPONSE_EXPECTED);

                    if (ret == DWT_SUCCESS)
                    {
                        /* 3. Wait for the Final message to arrive */
                        while (!((status_reg = dwt_read32bitreg(SYS_STATUS_ID)) & (SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR)))
                        { };

                        if (status_reg & SYS_STATUS_RXFCG_BIT_MASK)
                        {
                            /* Clear the RX event */
                            dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);
                            
                            uint32_t final_frame_len = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;
                            dwt_readrxdata(rx_buffer, final_frame_len, 0);

                            /* 4. Check if this is the Final message (0xE2) */
                            rx_buffer[ALL_MSG_SN_IDX] = 0;
                            if (memcmp(rx_buffer, rx_final_msg, ALL_MSG_COMMON_LEN) == 0)
                            {
                                uint32_t t_round1, t_reply2, t_reply1, t_round2;
                                uint64_t final_rx_ts;

                                /* Get Final RX timestamp */
                                final_rx_ts = get_rx_timestamp_u64();

                                /* Extract T_round1 and T_reply2 (sent by Initiator) */
                                resp_msg_get_ts(&rx_buffer[FINAL_MSG_T_ROUND_1_IDX], &t_round1);
                                resp_msg_get_ts(&rx_buffer[FINAL_MSG_T_REPLY_2_IDX], &t_reply2);

                                /* Calculate local values T_reply1 and T_round2 */
                                t_reply1 = (uint32_t)(resp_tx_ts - poll_rx_ts);
                                t_round2 = (uint32_t)(final_rx_ts - resp_tx_ts);

                                /* 5. RUN THE DS-TWR EQUATION */
                                // Formula: (T_round1 * T_round2 - T_reply1 * T_reply2) / (T_round1 + T_round2 + T_reply1 + T_reply2)
                                double num = (double)t_round1 * t_round2 - (double)t_reply1 * t_reply2;
                                double den = (double)t_round1 + t_round2 + t_reply1 + t_reply2;
                                
                                tof = num / den;
                                distance = tof * DWT_TIME_UNITS * SPEED_OF_LIGHT;

                                /* Display the result! */
                                Serial.print("DIST: "); Serial.print(distance); Serial.println(" m");
                            }
                        }
                        frame_seq_nb++;
                    }
                }
            }
        }
        else
        {
            /* Clear RX error events in the DW IC status register. */
            dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_ERR);
        }
}




