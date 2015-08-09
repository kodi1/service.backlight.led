/*
 * led.c
 *
 *  Created on: Jun 10, 2015
 *      Author: virtual
 */

//http://horrorcoding.altervista.org/arduino-development-with-eclipse-a-step-by-step-tutorial-to-the-basic-setup/

#include <stdint.h>
#include <avr/io.h>
#include <util/delay.h>
#include <avr/interrupt.h>
#include <stdio.h>
#include <string.h>
#include <stdio.h>
#include <avr/sleep.h>

#define USART_BAUDRATE 500000
#define BAUD_PRESCALE (((F_CPU/((USART_BAUDRATE*16UL)>>1)))-1)

/*
 * D09      PB1     PCINT1  LED_IN
 * D10      PB2     SS      LED_SS
 * D11      PB3     MOSI    LED_OUT
 * D13      PB5     CLK     LED_CLOCK
 */

#define RX_BUFF_SIZE    (1<<4)
#define TX_BUFF_SIZE    (1<<4)
#define SPI_BUFF_SIZE   (1<<9)
#define STR_RX_SIZE     (RX_BUFF_SIZE+2)
#define STR_TX_SIZE     (TX_BUFF_SIZE+2)

/* Led commands */
#define INT16FROMCHAR(a,b) ((a <<8 )|b)

/* Number of colors*/
#define LED_DATA_SIZE   (3)

#define LED_COUNT       "ledc"
#define LED_COUNT_DATA  (0x55)
#define LED_COUNT_MAX   (LED_DATA_SIZE * 200)

#define LED_TEST        "ledt"
#define LED_TEST_CNT    (4)
#define LED_TEST_R      (0x40)
#define LED_TEST_G      (0xf0)
#define LED_TEST_B      (0x80)

#define LED_CMD_CONTROL INT16FROMCHAR(0xaa, 0x55)
#define LED_DATA_END    INT16FROMCHAR(0x55, 0xaa)
#define CMD_DATA        INT16FROMCHAR('0','0')

#define TMR0_CNT        (100)
#define TMR0_CNT_CONT   (157)
#define TMR0_CNT_CORR   (82)
#define LED_TIMEOUT_SEC (2)

typedef enum {
    UART_STATE_IDLE,
    UART_STATE_CMD_BEGIN,
    UART_STATE_CMD,
    UART_STATE_LED_CMD,
    UART_STATE_LED_DATA_SIZE_1,
    UART_STATE_LED_DATA_SIZE_2,
    UART_STATE_LED_DATA_BEGIN,
    UART_STATE_LED_DATA_END,
} uart_state_t;

typedef enum {
    SPI_MODE_IDLE,
    SPI_MODE_DETECT,
    SPI_MODE_NORMAL,
} spi_state_t;

typedef struct {
    uint16_t    size;
    uint16_t    tail;
    uint16_t    head;
    char        *data;
} ring_t;

volatile    ring_t buff_tx, buff_rx, buff_spi;
volatile    uart_state_t uart_state;
volatile    spi_state_t spi_state;
volatile    uint8_t time_out_sec_cnt, tmr0_compa_isr_cnt;
uint16_t    raw_16, rx_cnt, led_cnt;
uint8_t     have_cmd;

char tx_data[TX_BUFF_SIZE];
char rx_data[RX_BUFF_SIZE];
char spi_data[SPI_BUFF_SIZE];
char str_rx[STR_RX_SIZE];
char str_tx[STR_TX_SIZE];

char ring_get(volatile ring_t *b)
{
    unsigned char ch = 0;
    if (b->tail != b->head) {
      ch = b->data[b->tail];
      b->tail++;
      b->tail &= (b->size-1);
    }
    return ch;
}

char ring_put(volatile ring_t *b, char data)
{
    unsigned short next = (b->head + 1) & (b->size-1);
    // do not overflow the buffer
    if (next != b->tail) {
        b->data[b->head] = data;
        b->head = next;
    } else {
        return -1;
    }
    return 0;
}

void put_srt(char *s)
{
    while (*s) {
        while(ring_put(&buff_tx, *s));
        s++;
    }
    UCSR0B |= _BV(UDRIE0);
}

void get_srt(char *s)
{
    do {
        *s = ring_get(&buff_rx);
    } while (*s++);
}

uint8_t ring_spi_get(char *ch)
{
    unsigned char ret = 0;
    // LEDs control data transmission
    if(buff_spi.tail != buff_spi.head) {
        *ch = buff_spi.data[buff_spi.tail];
        buff_spi.tail++;
        buff_spi.tail &= (buff_spi.size-1);
    } else {
        ret = 1;
    }
    return ret;
}

static inline void spi_trigger_tx(spi_state_t x)
{
    char _ch = SPDR;
    spi_state = x;
    PORTB &= ~_BV(PORTB2);
    SPCR |= _BV(SPIE)|_BV(SPE);
    ring_spi_get(&_ch);
    SPDR = _ch;
}

static inline void spi_stop_tx()
{
    PORTB |= _BV(PORTB2);
    SPCR &= ~_BV(SPE) & ~_BV(SPIE);
    spi_state = SPI_MODE_IDLE;
}

void enable_timeout_count (void)
{
    OCR0A = TMR0_CNT_CORR-1 + TCNT0;

    // Clear interrupt flag
    TIFR0 &= ~_BV(OCF0A);

    // enable ISR
    TIMSK0 |= _BV(OCIE0A);
}

void disable_timeout_count (void)
{
    // Disable Timer0 Compare A ISR
    time_out_sec_cnt = tmr0_compa_isr_cnt = 0;
    TIMSK0 &= ~_BV(OCIE0A);
}

void hw_setup(void)
{
    // Setup buffers
    buff_rx.data = rx_data;
    buff_rx.size = RX_BUFF_SIZE;

    buff_tx.data = tx_data;
    buff_tx.size = TX_BUFF_SIZE;

    buff_spi.data = spi_data;
    buff_spi.size = SPI_BUFF_SIZE;

    // Configure PCINT1 interrupt
    DDRB &= ~_BV(DDB1);
    PCMSK0 |= _BV(PCINT1);
    PCIFR &= ~_BV(PCIF0);
    PCICR |= _BV(PCIE0);

    // Set MOSI, SS and SCK output, all others input
    DDRB |= _BV(DDB3)|_BV(DDB5)|_BV(DDB2);
    DDRB &= ~_BV(DDB4);
    spi_stop_tx();

    // Enable SPI, Master, set clock rate fck/16, interrupt enable
    SPSR |= _BV(SPI2X); // speed x2
    SPCR = _BV(MSTR)|_BV(SPR0);

    // Configure ports double mode
    UCSR0A |= _BV(U2X0);

    // Configure the ports speed
    UBRR0H  = (BAUD_PRESCALE >> 8);
    UBRR0L  = BAUD_PRESCALE;

    // Asynchronous, 8N1 mode
    UCSR0C |= _BV(UCSZ00)|_BV(UCSZ01);

    // Rx/Tx hardware enable
    UCSR0B |= _BV(RXEN0);
    UCSR0B |= _BV(TXEN0);

    // Enable Rx/Tx interrupts
    UCSR0B |= _BV(UDRIE0);
    UCSR0B |= _BV(RXCIE0);

    // Set pin 0 of PORTB for output
    DDRB |= _BV(DDB0);

    // Setup sleep mode
    set_sleep_mode(SLEEP_MODE_IDLE);

    // compareA not port connected
    TCCR0A = 0;

    // Timer0 compareA setup clock rate fck/1024
    TCCR0B = _BV(CS02)|_BV(CS00);

    enable_timeout_count();

    // Enable interrupts

    sei();

    // Trigger SPI to try count leds
    ring_put(&buff_spi, LED_COUNT_DATA);
    spi_trigger_tx(SPI_MODE_DETECT);
}

void get_next_state(void)
{
    switch (raw_16) {
        case LED_CMD_CONTROL:
            uart_state = UART_STATE_LED_CMD;
            break;
        case CMD_DATA:
            uart_state = UART_STATE_CMD_BEGIN;
            break;
        case LED_DATA_END:
            uart_state = UART_STATE_LED_DATA_END;
            break;
        default:
            uart_state = UART_STATE_IDLE;
            break;
    }
}

// SPI Transmission/reception complete ISR
ISR(SPI_STC_vect, ISR_BLOCK)
{
    char ch = SPDR;
    if (SPI_MODE_NORMAL == spi_state) {
        // LEDs control data transmission
        if(ring_spi_get(&ch)) {
            // Control data was send interrupt disable
            goto COMPLETE;
        }
    } else {
        // Count leds
        ch = LED_COUNT_DATA;
        if(led_cnt++ > LED_COUNT_MAX) {
            led_cnt = 0;
            put_srt("No led cnt!\n");
            spi_state = SPI_MODE_NORMAL;
            goto COMPLETE;
        }
    }

    SPDR = ch;
    return;

COMPLETE:
    spi_stop_tx();
}

// Pin change ISR
ISR(PCINT0_vect, ISR_BLOCK)
{
    if (PINB & _BV(PINB1)) {
        PCICR &= ~_BV(PCIE0);
        // Switch to normal operation
        spi_state = SPI_MODE_NORMAL;
        led_cnt /= LED_DATA_SIZE;
    }
}

// Serial reception ISR
ISR(USART_RX_vect, ISR_BLOCK)
{
    // UCSR0A must be read before UDR0 !!!
    char ch = UDR0;

    // Clear timeout timer
    time_out_sec_cnt = 0;

    if (bit_is_clear(UCSR0A, FE0)) {
        // must read the data in order to clear the interrupt flag
        raw_16 = raw_16 << 8;
        raw_16 |= ch;

        if (UART_STATE_IDLE == uart_state) {
            get_next_state();
        }

        switch (uart_state) {
            case UART_STATE_LED_CMD:
                put_srt("Cmd\n");
                raw_16 = 0;
                uart_state = UART_STATE_LED_DATA_SIZE_1;
                break;
            case UART_STATE_LED_DATA_SIZE_1:
                put_srt("Size\n");
                uart_state = UART_STATE_LED_DATA_SIZE_2;
                break;
            case UART_STATE_LED_DATA_SIZE_2:
                rx_cnt = raw_16;
                uart_state = UART_STATE_LED_DATA_BEGIN;
                put_srt("Begin\n");
                raw_16 = 0;
                break;
            case UART_STATE_LED_DATA_BEGIN:
                ring_put(&buff_spi, ch);
                if (!--rx_cnt) {
                    put_srt("End\n");
                    uart_state = UART_STATE_IDLE;
                    raw_16 = 0;
                }
                break;
            case UART_STATE_LED_DATA_END:
                // Trigger SPI and enable interrupt
                put_srt("Trigger\n");
                spi_trigger_tx(SPI_MODE_NORMAL);
                uart_state = UART_STATE_IDLE;
                raw_16 = 0;
                break;
            case UART_STATE_CMD_BEGIN:
                uart_state = UART_STATE_CMD;
                break;
            case UART_STATE_CMD:
                ring_put(&buff_rx, ch);
                if ((ch == '\r') || (ch == '\n')) {
                    ring_put(&buff_rx, 0x0);
                    uart_state = UART_STATE_IDLE;
                    raw_16 = 0;
                    have_cmd = 1;
                }
                break;
            default:
              break;
        }
    } else {
        uart_state = UART_STATE_IDLE;
        raw_16 = 0;
    }
}

// Serial transmit empty ISR
ISR(USART_UDRE_vect, ISR_BLOCK)
{
    if (buff_tx.head != buff_tx.tail) {
        UDR0 = buff_tx.data[buff_tx.tail];
        buff_tx.tail++;
        buff_tx.tail &= (TX_BUFF_SIZE-1);
    } else {
        // Disable transmit empty ISR
        UCSR0B &= ~_BV(UDRIE0);
    }
}

// TMR0 CompareA ISR
ISR(TIMER0_COMPA_vect, ISR_BLOCK)
{
    tmr0_compa_isr_cnt ++;
    tmr0_compa_isr_cnt %= TMR0_CNT;

    if (tmr0_compa_isr_cnt) {
        OCR0A = TMR0_CNT_CONT-1 + TCNT0;
    } else {
        OCR0A = TMR0_CNT_CORR-1 + TCNT0;
        time_out_sec_cnt ++;
    }
}

void live_led(void)
{
    // Set pin 0 high to turn led on */
    PORTB |= _BV(PORTB0);
    _delay_ms(500);
    // Set pin 0 low to turn led off */
    PORTB &= ~_BV(PORTB0);
}

// Entry point
int main (void) {
    hw_setup();
    // Loop
    put_srt("Led start\n");
    for (;;) {
        if (have_cmd) {
            have_cmd = 0;

            enable_timeout_count();

            get_srt(str_rx);
            // Do echo
            snprintf(str_tx, sizeof(str_tx), "Echo %s", str_rx);
            put_srt(str_tx);

            if (!strncmp (str_rx, LED_COUNT, strlen(LED_COUNT))) {
                snprintf(str_tx, sizeof(str_tx), "leds cnt: %d\n", led_cnt);
                put_srt(str_tx);
            }

            if (!strncmp (str_rx, LED_TEST, strlen(LED_TEST))) {
                if (!led_cnt) {
                    led_cnt = LED_TEST_CNT;
                }

                for (uint16_t i = 0; i < led_cnt; i++) {
                    ring_put(&buff_spi, LED_TEST_B);
                    ring_put(&buff_spi, LED_TEST_G);
                    ring_put(&buff_spi, LED_TEST_R);
                }

                // Trigger SPI and enable interrupt
                spi_trigger_tx(SPI_MODE_NORMAL);
            }
        }

        if (LED_TIMEOUT_SEC <= time_out_sec_cnt) {
            disable_timeout_count();
            // Power down Leds
            for (uint16_t i = 0; i < led_cnt; i++) {
                ring_put(&buff_spi, 0x00);
                ring_put(&buff_spi, 0x00);
                ring_put(&buff_spi, 0x00);
            }
            // Trigger SPI and enable interrupt
            spi_trigger_tx(SPI_MODE_NORMAL);
        }
//#define DBG_SPI
#ifdef DBG_SPI
        {
        static uint8_t dbg = 0;
        if (time_out_sec_cnt) {
            time_out_sec_cnt = 0;
            if (dbg%2) {
                for (uint16_t i = 0; i < led_cnt; i++) {
                    ring_put(&buff_spi, LED_TEST_R);
                    ring_put(&buff_spi, LED_TEST_G);
                    ring_put(&buff_spi, LED_TEST_B);
                }
            } else {
                for (uint16_t i = 0; i < led_cnt; i++) {
                    ring_put(&buff_spi, 0xaa);
                    ring_put(&buff_spi, 0x55);
                    ring_put(&buff_spi, 0x00);
                }
            }
            dbg++;
            // Trigger SPI and enable interrupt
            spi_trigger_tx(SPI_MODE_NORMAL);
        }
        }
#endif
        if (SPI_MODE_IDLE == spi_state) {
            sleep_mode();
        }
    }
}
