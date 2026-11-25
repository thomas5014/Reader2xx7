// main.c -- bare-metal (no MicroPython) firmware for RPR480: display +
// touch + LVGL, running the same C drivers proven in the MicroPython build
// (nt35510_c/, cst3240_c/) with no interpreter, VM, or REPL underneath.
//
// Architecture, compared to the MicroPython version (modlvport.c):
//   - There's no mp_obj_t wrapping, no qstr table, no GC heap. Every
//     function here is just a C function; main() is the actual entry
//     point (the chip's boot ROM calls it directly, via a small pico-sdk
//     runtime that sets up the stack and clocks first), not something
//     invoked from a Python bytecode loop.
//   - LVGL's single global state struct lives in .bss as an ordinary
//     static variable (see lv_conf.h: LV_ENABLE_GLOBAL_CUSTOM is left at
//     its default of 0), initialized once by lv_init() and never torn
//     down -- there's no soft reset here to tear it down *for*.
//   - stdio_init_all() wires libc's printf to USB CDC via TinyUSB. That's
//     the same underlying transport MicroPython's REPL used, and it has
//     the same fundamental limitation we hit repeatedly debugging the
//     MicroPython build: a printf that's still queued when the board
//     hard-faults may never reach the host. Removing MicroPython doesn't
//     fix that by itself -- the real fix, if this comes up again, is a
//     debug probe (SWD) or a polled (non-USB) UART for crash-path logging.
//   - There's no REPL at all. Every change here means edit -> rebuild ->
//     reflash -> observe, not "type one line and see what happens". That
//     trade (lose interactive testing, gain a much lighter, fully-C image
//     with none of the MicroPython-specific failure modes we spent a lot
//     of time on) is the whole point of this experiment.
//
// What's deliberately NOT here yet, to keep this first skeleton small:
//   - CYW43 / WiFi -- not linked in at all. --- scary shit
// All three are addable later the same way nt35510_c/cst3240_c were: pull
// the existing C code in, write whatever small amount of glue main() needs.

#include <stdio.h>

#include "pico/stdlib.h"
#include "hardware/pwm.h"
#include "hardware/clocks.h"

#include "lvgl/lvgl.h"
#include "nt35510_c/nt35510.h"
#include "cst3240_c/cst3240.h"
#include "RV3028.h"
#include "INA226.h"
#include "WS2818.h"
#include "LIS2DW12.h"
#include "SDIO.h"
#include "DRV2605L.h"
#include "PSRAM.h"
#include "ff.h"

#define PSRAMSC_PIN 47

static FATFS fs;

#define BACKLIGHT_PIN 20
#define SYSPWROFF_PIN 40

#define LV_W 480
#define LV_H 800

// One partial-render buffer, 80 lines (76.8 KB) -- same size/strategy as
// modlvport.c: render a horizontal strip, blocking-DMA it out, repeat.
// Double-buffering (render the next strip while the DMA for the last one
// is still running) is the natural next speed step once this works, but
// adds real complexity (the flush callback can no longer just block until
// the DMA finishes) -- deliberately left for later.
#define LV_BUF_LINES 80

static uint8_t draw_buf[LV_W * LV_BUF_LINES * 2] __attribute__((aligned(64)));

// --- LVGL <-> hardware glue -------------------------------------------

// LVGL calls this to find out "how much time has passed" -- it has no
// notion of real time on its own. pico-sdk's to_ms_since_boot/get_absolute_time
// is the bare-metal equivalent of MicroPython's mp_hal_ticks_ms() (which
// modlvport.c's tick_cb used).
static uint32_t tick_cb(void) {
    return to_ms_since_boot(get_absolute_time());
}

// Called by LVGL whenever a rendered area needs to reach the physical
// screen. Identical in spirit to modlvport.c's flush_cb: hand the pixels to
// the PIO/DMA driver, block until it's done, then tell LVGL the buffer is
// free to reuse. The "blocking" part is exactly what double-buffering would
// remove later.
static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    nt35510_draw_buf_dma(area->x1, area->y1,
                         lv_area_get_width(area), lv_area_get_height(area),
                         (const uint16_t *)px_map);
    lv_display_flush_ready(disp);
}

// Sends kill interrupt to sys pwr switch
static void sys_power_off(lv_event_t *e) {
    lv_event_code_t code = lv_event_get_code(e);

    if (code == LV_EVENT_CLICKED) {
        // init system power kill pin, active low
        gpio_init( SYSPWROFF_PIN);
        gpio_set_dir( SYSPWROFF_PIN, GPIO_OUT);
        gpio_put(SYSPWROFF_PIN, 0);
    };
}

// Called by LVGL periodically to ask "is a finger down, and where". Same
// cst3240_read() the MicroPython build's touch_read_cb used.
static void touch_read_cb(lv_indev_t *indev, lv_indev_data_t *data) {
    (void)indev;
    int x, y;
    if (cst3240_read(&x, &y)) {
        data->point.x = x;
        data->point.y = y;
        data->state = LV_INDEV_STATE_PRESSED;
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

static void backlight_init(void) {
    gpio_set_function(BACKLIGHT_PIN, GPIO_FUNC_PWM);
    uint slice = pwm_gpio_to_slice_num(BACKLIGHT_PIN);
    // 50 kHz, matching the PWM(Pin(20)); backlight.freq(50_000) used
    // throughout the Python/MicroPython testing this project -- picked
    // there to be well above audible/flicker range for the LED driver.
    // clk_sys is 125 MHz at the pico-sdk default boot clock (machine.freq()
    // was never called from C here) / (wrap+1) / (clkdiv) = PWM frequency;
    // wrap=1999, clkdiv=1.0 -> 125e6 / 2000 = 62.5 kHz, close enough.
    pwm_set_wrap(slice, 1999);
    pwm_set_clkdiv(slice, 1.0f);
    pwm_set_gpio_level(BACKLIGHT_PIN, 1999);  // full brightness
    pwm_set_enabled(slice, true);
}

// --- Demo screen (same widgets as modlvport.c's lvport_demo) -----------

static void btn_event_cb(lv_event_t *e) {
    static int taps;
    lv_obj_t *label = lv_event_get_user_data(e);
    lv_label_set_text_fmt(label, "Tapped %d", ++taps);
    lis2dw12_data_t data;
    lis2dw12_get(&data);
    printf("x: %d, y: %d, z: %d \n", data.x, data.y, data.z);
}

static void slider_event_cb(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_target(e);
    lv_obj_t *label = lv_event_get_user_data(e);
    lv_label_set_text_fmt(label, "%d%%", (int)lv_slider_get_value(slider));
}

// Haptic label cb
static void buzz_slide_cb(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_target(e);
    lv_obj_t *label = lv_event_get_user_data(e);
    lv_label_set_text_fmt(label, "%d", (int)lv_slider_get_value(slider));
}

// Haptic buzz cb
static void buzz_btn_cb(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_user_data(e);
    drv2605l_raw((uint8_t)lv_slider_get_value(slider));
}

// Color sliders and swatch vars
static uint8_t s_red, s_green, s_blue;
static uint8_t sld_ids[3] = {0,1,2};
static lv_obj_t *s_swatch;

// Updates color swatch and ws2818 indicator led
static void color_slider_event_cb(lv_event_t *e) {
    lv_obj_t *slider = lv_event_get_target(e);
    uint8_t *channel = lv_event_get_user_data(e);
    uint8_t value = (uint8_t)lv_slider_get_value(slider);

    switch (*channel) {
        case 0: s_red   = value; break;
        case 1: s_green = value; break;
        case 2: s_blue  = value; break;
    }

    lv_obj_set_style_bg_color(s_swatch, lv_color_make(s_red, s_green, s_blue), 0);
    ws2818_set_color(s_red, s_green, s_blue);
}

// Color sliders for ws2818 led
// partitioned portion of demo screen
static void color_sliders(lv_obj_t *scr) {
    // this is making me itch to use structs
    uint8_t red   = 0;
    uint8_t green = 0;
    uint8_t blue  = 0;
    for (int i = 0; i < 3; i++) { // color sliders and their value labels
        uint16_t y = 420 + i * 40;

        lv_obj_t *slider = lv_slider_create(scr);
        lv_slider_set_range(slider, 0, 255);
        lv_obj_set_width(slider, 360);
        lv_obj_align(slider, LV_ALIGN_TOP_LEFT, 40, y);
        lv_obj_add_event_cb(slider, color_slider_event_cb, LV_EVENT_VALUE_CHANGED, &sld_ids[i]);

        lv_obj_t *val = lv_label_create(scr);
        lv_obj_set_style_text_color(val, lv_color_hex(0xE8ECF0), 0);
        lv_label_set_text(val, "0%");
        lv_obj_align_to(val, slider, LV_ALIGN_OUT_RIGHT_MID, 20, 0);
        lv_obj_add_event_cb(slider, slider_event_cb, LV_EVENT_VALUE_CHANGED, val);
    }

    //Swatch
    s_swatch = lv_obj_create(scr);
    lv_obj_set_size(s_swatch, 80, 80);
    lv_obj_set_style_radius(s_swatch, 12, 0);   // rounded rect
    lv_obj_set_style_bg_color(s_swatch, lv_color_make(0, 0, 0), 0);
    lv_obj_align(s_swatch, LV_ALIGN_TOP_MID, 0, 300);  // wherever fits near the sliders
}

// pulls time data from rtc chip, sets text at bottom of ui -- this is an updating cb
static void clock_timer_cb(lv_timer_t * timer) {
    lv_obj_t *time_text = lv_timer_get_user_data(timer);
    rv3028_time_t t;
    if (rv3028_read_time(&t)) {
        lv_label_set_text_fmt(time_text, "Time: %04u-%02u-%02u %02u:%02u:%02u (weekday %u)\n",
            t.year, t.month, t.date, t.hour, t.minute, t.second, t.weekday);
    }
}

static lis2dw12_data_t max_accs;

// Updates accelerometer data text
static void accel_timer_cb(lv_timer_t *timer) {
    lv_obj_t *accel_text = lv_timer_get_user_data(timer);
    lis2dw12_data_t data;
    lis2dw12_get(&data);
    if (data.x > max_accs.x) max_accs.x = data.x;
    if (data.y > max_accs.y) max_accs.y = data.y;
    if (data.z > max_accs.z) max_accs.z = data.z;
    lv_label_set_text_fmt(accel_text, "x:%d y:%d z:%d \nmax: x:%d y:%d z:%d", data.x, data.y, data.z, max_accs.x, max_accs.y, max_accs.z);
}


static void build_demo_screen(void) {
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x101418), 0);

    // A name. ex: hi my name is, Floccinaucinihilipilification
    lv_obj_t *title = lv_label_create(scr);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(title, lv_color_hex(0xE8ECF0), 0);
    lv_label_set_text(title, "Reader2xx7 (bare metal)");
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 30);

    // Test button, tap and tap some more
    lv_obj_t *btn = lv_button_create(scr);
    lv_obj_set_size(btn, 260, 90);
    lv_obj_align(btn, LV_ALIGN_TOP_MID, 0, 80);
    lv_obj_t *btn_label = lv_label_create(btn);
    lv_obj_set_style_text_font(btn_label, &lv_font_montserrat_24, 0);
    lv_label_set_text(btn_label, "Tap me");
    lv_obj_center(btn_label);
    
    // Displays current number of button taps - just the one button
    lv_obj_t *count = lv_label_create(scr);
    lv_obj_set_style_text_font(count, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(count, lv_color_hex(0xE8ECF0), 0);
    lv_label_set_text(count, "Tapped 0");
    lv_obj_align(count, LV_ALIGN_TOP_MID, 0, 200);
    lv_obj_add_event_cb(btn, btn_event_cb, LV_EVENT_CLICKED, count);

    // Color indicator sliders - control the rainbow!
    color_sliders(scr);

    // Test switch, no functionality
    lv_obj_t *sw = lv_switch_create(scr);
    lv_obj_align(sw, LV_ALIGN_TOP_MID, 0, 580);
    
    // Test list, no functionality
    lv_obj_t *lst = lv_list_create(scr);
    lv_obj_set_align(lst, LV_ALIGN_BOTTOM_MID);
    lv_obj_set_size(lst, 400, 150);
    lv_obj_set_style_bg_color(lst, lv_color_hex(0x202020), 0);
    // lv_obj_set_st
    lv_obj_t *list_title = lv_list_add_text(lst, "List Items:");
    lv_list_add_button(lst, LV_SYMBOL_FILE, "New");
    lv_list_add_button(lst, LV_SYMBOL_EDIT, "Edit");
    lv_list_add_button(lst, LV_SYMBOL_BATTERY_1, "Battery");
    lv_list_add_button(lst, LV_SYMBOL_BLUETOOTH, "Bluetooth");

    // test drop down, no functionality
    lv_obj_t *thing2 = lv_dropdown_create(scr);
    lv_obj_align(thing2,LV_ALIGN_TOP_LEFT, 10, 40);
    lv_obj_set_x(thing2, 20);
    lv_obj_set_width(thing2, 80);
    lv_dropdown_set_dir(thing2, LV_DIR_RIGHT);
    lv_dropdown_add_option(thing2,"thing1\nthing2\nthing3\nthing4",0);

    // It's a power button, click and you ded - wel temporaly
    lv_obj_t *powerbtn = lv_btn_create(scr);
    lv_obj_set_align(powerbtn, LV_ALIGN_TOP_RIGHT);
    lv_obj_set_size(powerbtn, 60, 60);
    lv_obj_set_style_radius(powerbtn, 25, 0);
    lv_obj_t *pwrlabel = lv_label_create(powerbtn);
    lv_obj_set_align(pwrlabel, LV_ALIGN_CENTER);
    lv_label_set_text(pwrlabel, LV_SYMBOL_POWER);
    lv_obj_add_event_cb(powerbtn, *sys_power_off, LV_EVENT_CLICKED, NULL);

    // Create a clock that updates every 1000 ms (1 second)
    lv_obj_t *time_text = lv_label_create(scr);
    lv_obj_set_style_text_font(time_text, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(time_text, lv_color_hex(0xE8ECF0), 0);
    lv_label_set_text(time_text, "'time goes here'");
    lv_obj_align(time_text, LV_ALIGN_BOTTOM_LEFT, 0, 190);

    lv_timer_t *timer = lv_timer_create(clock_timer_cb, 1000, time_text);

    // accelerometer readouts
    lv_obj_t *accel_text = lv_label_create(scr);
    lv_obj_set_style_text_font(accel_text, &lv_font_montserrat_24, 0);
    lv_obj_set_style_text_color(accel_text, lv_color_hex(0xE8ECF0), 0);
    lv_label_set_text(accel_text, "accel: ...");
    lv_obj_align(accel_text, LV_ALIGN_BOTTOM_LEFT, 0, 220);

    lv_timer_create(accel_timer_cb, 100, accel_text);  // e.g. 10Hz, faster than the 1Hz clock

    // Haptic tone picker slider and label for tone number
    lv_obj_t *buzz_slide = lv_slider_create(scr);
    lv_slider_set_range(buzz_slide, 1, 123);
    lv_obj_set_width(buzz_slide, 340);
    lv_obj_align(buzz_slide, LV_ALIGN_BOTTOM_LEFT, 20, 90); 
    lv_obj_t *buzzbtn = lv_btn_create(scr);
    lv_obj_set_size(buzzbtn, 100, 30);
    lv_obj_align_to(buzzbtn,buzz_slide, LV_ALIGN_RIGHT_MID, 100, 0);
    lv_obj_t *buzzlabel = lv_label_create(buzzbtn);
    lv_obj_center(buzzlabel);
    lv_obj_set_style_text_font(buzzlabel, &lv_font_montserrat_24, 0);
    lv_label_set_text(buzzlabel,"0");
    lv_obj_add_event_cb(buzz_slide, buzz_slide_cb, LV_EVENT_VALUE_CHANGED, buzzlabel);
    lv_obj_add_event_cb(buzzbtn, buzz_btn_cb, LV_EVENT_CLICKED, buzz_slide);

} 

int main(void) {
    stdio_init_all();

    // A short pause so there's a chance of a host terminal already being
    // attached by the time the first printf runs -- with no REPL to
    // reconnect to later, there's no second chance to catch early output
    // the way re-running a script could in the MicroPython build.
    sleep_ms(1500);
    printf("rpr480 bare-metal: boot\n");
    printf("start up system clock: %dmhz/n",clock_get_hz(clk_sys)/1000000);

    // Start 16bit parallel communication with display panel
    // DMA and PIO protocalls initialized for zero cpu overhead bit banging
    // backlight only turned on later, this is in part to avoid showing gram noise
    nt35510_init();
    printf("nt35510_init done\n");

    // External memory device - shares same bus as flash, select pin is 47
    // Will later be used for large multi-page buff, current it is fine if it fails in an expected manor, there are still instances where it will just hang tho
    printf("Bringing up PSRAM...\n"); // should the following be in a function?... yeah, prob
    int psram_size = psram_bringup(PSRAMSC_PIN);
    printf("psram_brignup done, size: %d\n",psram_size); // 8,388,608 8,388,608
    sleep_ms(100);
    if (psram_size != 0) {
        volatile uint8_t *psram = (volatile uint8_t *)PSRAM_BASE;
        psram[0] = 0x42;
        printf("psram readback: 0x%02x\n",psram[0]);
    } else {
        printf("PSRAM not detected, skipping readback test\n");
    }

    // Touch panel, first device on I2C1 - sets clock to 400khz, on gpio30-31
    // device adress: 0x5A, LVGL handlers pull state regularly to parse gestures, no additional parsers needed
    cst3240_init();
    printf("cst3240_init done\n");
    
    // individual addressable rgb indicator led, controlled over pio on gpio 44
    // not core to system function
    if (ws2818_init()) {
        printf("ws2818_init done\nsetting color...\n");
        ws2818_set_color(255,0,0);
        printf("color set to red\n");
    } else {
        printf("ws2818_init failed\n");
    }

    // Accelerometer, I2C1 - same a touch panel, addr = 0x18
    // returns x,y,z accelerations in type lis2dw12_data_t. 1g ~ 2^12
    // Has temperature reading too. not part of lis2dw12_data_t yet
    lis2dw12_init();
    printf("lis2dw12_init done\n");
    sleep_ms(50);
    lis2dw12_data_t data;
    lis2dw12_get(&data);
    max_accs = data;
    printf("x: %d, y: %d, z: %d \n", data.x, data.y, data.z);

    // Test for both the pio sdio protocall and fatfs mounting of said sdio attached drive
    // Presently very bare-bones: no physical card detection gpio 21, ..., and uhh other things too.
    // With the connecting of the card, it will be mounted then opened to the base dir and the contents will be printed out -- man someone cant think of a more inteligent way of stating that
    if (sdio_sdcard_init()) {
        printf("SDIO: card ready, %lu sectors\n", (unsigned long)sdio_sdcard_sector_count());
        
        // Creating/Mounting file system
        printf("Mounting sd card:\n");
        FRESULT result = f_mount(&fs);
        printf("Mount result: %d - %d\n",result,result==FR_OK);
        FILINFO fno; FF_DIR dir;
        printf("Opening dir\n");
        f_opendir(&fs, &dir, "/");
        printf("Printing dir contents:\n");
        // printing all contents 
        while (true) {
            result = f_readdir(&dir, &fno);
            if (result != FR_OK || fno.fname[0] == 0) break;
            printf("  %s\n", fno.fname);
        }
        printf("Closing link to dir\n");
        f_closedir(&dir);
    } else {
        printf("SDIO: init failed\n");
    }

    // Haptic driver, I2C0 - gpio28-29, address is 0x5A(same as touch but this is a different bus so it's fine)
    // idk what else to say, it's all just feels dude
    drv2605l_init();
    printf("drv2605l_init done\n");
    // haptic_buzz(); // this is commented out right now because later the lvgl ui will have a section for testing this


    // First real test of the new driver, deliberately standalone: print
    // once and move on, before anything display/LVGL-related runs. Same
    // "verify in isolation before wiring it into the UI" approach used for
    // every driver so far -- if this printf never shows the right time
    // (or shows nothing), the problem is in RV3028.c/the I2C0 wiring, not
    // tangled up with display or LVGL behavior.
    //
    // rv3028_init() has to run before any other rv3028_* call -- it's what
    // actually configures I2C0 (clock, GPIO28/29 function select, pull-ups).
    // Forgetting it (as I did, first time through) means rv3028_read_time()
    // calls i2c_write_blocking/i2c_read_blocking against an unconfigured
    // peripheral; those are blocking calls that poll hardware status bits
    // waiting for a state that can't happen, so execution just stops dead
    // with no further output -- exactly "hangs right after cst3240_init
    // done" and nothing printed from the RTC path at all.
    rv3028_init();
    rv3028_time_t t;
    if (rv3028_read_time(&t)) {
        printf("RTC: %04u-%02u-%02u %02u:%02u:%02u (weekday %u)\n",
               t.year, t.month, t.date, t.hour, t.minute, t.second, t.weekday);
    } else {
        printf("RTC: read failed -- check I2C0 wiring (GPIO28 SDA/29 SCL) and address 0x52\n");
    }

    // System current sensor - I2C0 gpio28-29, device address = 0x40
    // placed between battery control chip and sys pwr switch. read voltage may be above true by ~0.1-0.2v
    ina226_init();
    printf("INA226: bus-v: %F, shunt-v: %F\n",ina226_bus_voltage(),ina226_shunt_voltage());

    // PWM en to led driver for backlight, gpio20
    // set to full brightness at the moment
    backlight_init();

    // lvgl system -- it does things, idk
    lv_init();
    lv_tick_set_cb(tick_cb);

    lv_display_t *disp = lv_display_create(LV_W, LV_H);
    lv_display_set_color_format(disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(disp, draw_buf, NULL, sizeof(draw_buf),
                           LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, flush_cb);

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touch_read_cb);

    printf("lv_init + display + indev done\n");
    build_demo_screen();
    printf("demo screen built, entering main loop\n");

    // The superloop: no RTOS, no interrupts driving LVGL -- just ask it
    // "anything to do?" on a steady cadence, forever. lv_timer_handler()
    // returns how long (ms) until it next needs attention; sleeping that
    // long instead of a fixed delay is the standard LVGL integration
    // pattern (avoids busy-waiting when nothing's animating).
    while (true) {
        uint32_t next_ms = lv_timer_handler();
        sleep_ms(next_ms ? next_ms : 5);
    }
}
