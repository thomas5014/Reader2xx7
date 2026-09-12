#include "nt35510.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include "boards/reader2350.h"

#define DATA_MASK (0xFFFFu << READER_LCD_PIN_D0)

// One bus write: put the 16-bit value on D0..D15, hold DC, strobe WR low->high.
// This is the direct GPIO-poke path only -- no PIO/DMA yet. It's slow (one
// gpio_put_masked + two gpio_put calls per pixel) but it's the version to
// bring up first, so a bug here can't be confused with a PIO/DMA bug later.
static inline void lcd_write16(uint16_t value, bool dc) {
    gpio_put(READER_LCD_PIN_DC, dc);
    gpio_put_masked(DATA_MASK, (uint32_t)value << READER_LCD_PIN_D0);
    gpio_put(READER_LCD_PIN_WR, 0);
    gpio_put(READER_LCD_PIN_WR, 1);
}

static inline void lcd_cmd(uint16_t cmd)  { lcd_write16(cmd, false); }
static inline void lcd_data(uint16_t d)   { lcd_write16(d, true); }

static void lcd_hw_reset(void) {
    gpio_put(READER_LCD_PIN_RST, 1); sleep_ms(50);
    gpio_put(READER_LCD_PIN_RST, 0); sleep_ms(50);
    gpio_put(READER_LCD_PIN_RST, 1); sleep_ms(120);
}

// NT35510 manufacturer register table -- ported 1:1 from nt35510.py's
// init_extra(). Opaque by design: these are panel-specific analog/gamma
// tuning values from the vendor init sequence, not something to hand-derive.
static void lcd_init_extra(void) {
    lcd_cmd(0xF000); lcd_data(0x55);
    lcd_cmd(0xF001); lcd_data(0xAA);
    lcd_cmd(0xF002); lcd_data(0x52);
    lcd_cmd(0xF003); lcd_data(0x08);
    lcd_cmd(0xF004); lcd_data(0x01);
    lcd_cmd(0xB600); lcd_data(0x34);
    lcd_cmd(0xB601); lcd_data(0x34);
    lcd_cmd(0xB602); lcd_data(0x34);
    lcd_cmd(0xB000); lcd_data(0x0D);
    lcd_cmd(0xB001); lcd_data(0x0D);
    lcd_cmd(0xB002); lcd_data(0x0D);
    lcd_cmd(0xB700); lcd_data(0x24);
    lcd_cmd(0xB701); lcd_data(0x24);
    lcd_cmd(0xB702); lcd_data(0x24);
    lcd_cmd(0xB100); lcd_data(0x0D);
    lcd_cmd(0xB101); lcd_data(0x0D);
    lcd_cmd(0xB102); lcd_data(0x0D);
    lcd_cmd(0xB800); lcd_data(0x24);
    lcd_cmd(0xB801); lcd_data(0x24);
    lcd_cmd(0xB802); lcd_data(0x24);
    lcd_cmd(0xB200); lcd_data(0x00);
    lcd_cmd(0xB900); lcd_data(0x24);
    lcd_cmd(0xB901); lcd_data(0x24);
    lcd_cmd(0xB902); lcd_data(0x24);
    lcd_cmd(0xB300); lcd_data(0x05);
    lcd_cmd(0xB301); lcd_data(0x05);
    lcd_cmd(0xB302); lcd_data(0x05);
    lcd_cmd(0xBA00); lcd_data(0x34);
    lcd_cmd(0xBA01); lcd_data(0x34);
    lcd_cmd(0xBA02); lcd_data(0x34);
    lcd_cmd(0xB500); lcd_data(0x0B);
    lcd_cmd(0xB501); lcd_data(0x0B);
    lcd_cmd(0xB502); lcd_data(0x0B);
    lcd_cmd(0xBC00); lcd_data(0x00);
    lcd_cmd(0xBC01); lcd_data(0xA3);
    lcd_cmd(0xBC02); lcd_data(0x00);
    lcd_cmd(0xBD00); lcd_data(0x00);
    lcd_cmd(0xBD01); lcd_data(0xA3);
    lcd_cmd(0xBD02); lcd_data(0x00);
    lcd_cmd(0xBE00); lcd_data(0x00);
    lcd_cmd(0xBE01); lcd_data(0x63);
    lcd_cmd(0xD100); lcd_data(0x00);
    lcd_cmd(0xD101); lcd_data(0x37);
    lcd_cmd(0xD102); lcd_data(0x00);
    lcd_cmd(0xD103); lcd_data(0x52);
    lcd_cmd(0xD104); lcd_data(0x00);
    lcd_cmd(0xD105); lcd_data(0x7B);
    lcd_cmd(0xD106); lcd_data(0x00);
    lcd_cmd(0xD107); lcd_data(0x99);
    lcd_cmd(0xD108); lcd_data(0x00);
    lcd_cmd(0xD109); lcd_data(0xB1);
    lcd_cmd(0xD10A); lcd_data(0x00);
    lcd_cmd(0xD10B); lcd_data(0xD2);
    lcd_cmd(0xD10C); lcd_data(0x00);
    lcd_cmd(0xD10D); lcd_data(0xF6);
    lcd_cmd(0xD10E); lcd_data(0x01);
    lcd_cmd(0xD10F); lcd_data(0x27);
    lcd_cmd(0xD110); lcd_data(0x01);
    lcd_cmd(0xD111); lcd_data(0x4E);
    lcd_cmd(0xD112); lcd_data(0x01);
    lcd_cmd(0xD113); lcd_data(0x8C);
    lcd_cmd(0xD114); lcd_data(0x01);
    lcd_cmd(0xD115); lcd_data(0xBE);
    lcd_cmd(0xD116); lcd_data(0x02);
    lcd_cmd(0xD117); lcd_data(0x0B);
    lcd_cmd(0xD118); lcd_data(0x02);
    lcd_cmd(0xD119); lcd_data(0x48);
    lcd_cmd(0xD11A); lcd_data(0x02);
    lcd_cmd(0xD11B); lcd_data(0x4A);
    lcd_cmd(0xD11C); lcd_data(0x02);
    lcd_cmd(0xD11D); lcd_data(0x7E);
    lcd_cmd(0xD11E); lcd_data(0x02);
    lcd_cmd(0xD11F); lcd_data(0xBC);
    lcd_cmd(0xD120); lcd_data(0x02);
    lcd_cmd(0xD121); lcd_data(0xE1);
    lcd_cmd(0xD122); lcd_data(0x03);
    lcd_cmd(0xD123); lcd_data(0x10);
    lcd_cmd(0xD124); lcd_data(0x03);
    lcd_cmd(0xD125); lcd_data(0x31);
    lcd_cmd(0xD126); lcd_data(0x03);
    lcd_cmd(0xD127); lcd_data(0x5A);
    lcd_cmd(0xD128); lcd_data(0x03);
    lcd_cmd(0xD129); lcd_data(0x73);
    lcd_cmd(0xD12A); lcd_data(0x03);
    lcd_cmd(0xD12B); lcd_data(0x94);
    lcd_cmd(0xD12C); lcd_data(0x03);
    lcd_cmd(0xD12D); lcd_data(0x9F);
    lcd_cmd(0xD12E); lcd_data(0x03);
    lcd_cmd(0xD12F); lcd_data(0xB3);
    lcd_cmd(0xD130); lcd_data(0x03);
    lcd_cmd(0xD131); lcd_data(0xB9);
    lcd_cmd(0xD132); lcd_data(0x03);
    lcd_cmd(0xD133); lcd_data(0xC1);
    lcd_cmd(0xD200); lcd_data(0x00);
    lcd_cmd(0xD201); lcd_data(0x37);
    lcd_cmd(0xD202); lcd_data(0x00);
    lcd_cmd(0xD203); lcd_data(0x52);
    lcd_cmd(0xD204); lcd_data(0x00);
    lcd_cmd(0xD205); lcd_data(0x7B);
    lcd_cmd(0xD206); lcd_data(0x00);
    lcd_cmd(0xD207); lcd_data(0x99);
    lcd_cmd(0xD208); lcd_data(0x00);
    lcd_cmd(0xD209); lcd_data(0xB1);
    lcd_cmd(0xD20A); lcd_data(0x00);
    lcd_cmd(0xD20B); lcd_data(0xD2);
    lcd_cmd(0xD20C); lcd_data(0x00);
    lcd_cmd(0xD20D); lcd_data(0xF6);
    lcd_cmd(0xD20E); lcd_data(0x01);
    lcd_cmd(0xD20F); lcd_data(0x27);
    lcd_cmd(0xD210); lcd_data(0x01);
    lcd_cmd(0xD211); lcd_data(0x4E);
    lcd_cmd(0xD212); lcd_data(0x01);
    lcd_cmd(0xD213); lcd_data(0x8C);
    lcd_cmd(0xD214); lcd_data(0x01);
    lcd_cmd(0xD215); lcd_data(0xBE);
    lcd_cmd(0xD216); lcd_data(0x02);
    lcd_cmd(0xD217); lcd_data(0x0B);
    lcd_cmd(0xD218); lcd_data(0x02);
    lcd_cmd(0xD219); lcd_data(0x48);
    lcd_cmd(0xD21A); lcd_data(0x02);
    lcd_cmd(0xD21B); lcd_data(0x4A);
    lcd_cmd(0xD21C); lcd_data(0x02);
    lcd_cmd(0xD21D); lcd_data(0x7E);
    lcd_cmd(0xD21E); lcd_data(0x02);
    lcd_cmd(0xD21F); lcd_data(0xBC);
    lcd_cmd(0xD220); lcd_data(0x02);
    lcd_cmd(0xD221); lcd_data(0xE1);
    lcd_cmd(0xD222); lcd_data(0x03);
    lcd_cmd(0xD223); lcd_data(0x10);
    lcd_cmd(0xD224); lcd_data(0x03);
    lcd_cmd(0xD225); lcd_data(0x31);
    lcd_cmd(0xD226); lcd_data(0x03);
    lcd_cmd(0xD227); lcd_data(0x5A);
    lcd_cmd(0xD228); lcd_data(0x03);
    lcd_cmd(0xD229); lcd_data(0x73);
    lcd_cmd(0xD22A); lcd_data(0x03);
    lcd_cmd(0xD22B); lcd_data(0x94);
    lcd_cmd(0xD22C); lcd_data(0x03);
    lcd_cmd(0xD22D); lcd_data(0x9F);
    lcd_cmd(0xD22E); lcd_data(0x03);
    lcd_cmd(0xD22F); lcd_data(0xB3);
    lcd_cmd(0xD230); lcd_data(0x03);
    lcd_cmd(0xD231); lcd_data(0xB9);
    lcd_cmd(0xD232); lcd_data(0x03);
    lcd_cmd(0xD233); lcd_data(0xC1);
    lcd_cmd(0xD300); lcd_data(0x00);
    lcd_cmd(0xD301); lcd_data(0x37);
    lcd_cmd(0xD302); lcd_data(0x00);
    lcd_cmd(0xD303); lcd_data(0x52);
    lcd_cmd(0xD304); lcd_data(0x00);
    lcd_cmd(0xD305); lcd_data(0x7B);
    lcd_cmd(0xD306); lcd_data(0x00);
    lcd_cmd(0xD307); lcd_data(0x99);
    lcd_cmd(0xD308); lcd_data(0x00);
    lcd_cmd(0xD309); lcd_data(0xB1);
    lcd_cmd(0xD30A); lcd_data(0x00);
    lcd_cmd(0xD30B); lcd_data(0xD2);
    lcd_cmd(0xD30C); lcd_data(0x00);
    lcd_cmd(0xD30D); lcd_data(0xF6);
    lcd_cmd(0xD30E); lcd_data(0x01);
    lcd_cmd(0xD30F); lcd_data(0x27);
    lcd_cmd(0xD310); lcd_data(0x01);
    lcd_cmd(0xD311); lcd_data(0x4E);
    lcd_cmd(0xD312); lcd_data(0x01);
    lcd_cmd(0xD313); lcd_data(0x8C);
    lcd_cmd(0xD314); lcd_data(0x01);
    lcd_cmd(0xD315); lcd_data(0xBE);
    lcd_cmd(0xD316); lcd_data(0x02);
    lcd_cmd(0xD317); lcd_data(0x0B);
    lcd_cmd(0xD318); lcd_data(0x02);
    lcd_cmd(0xD319); lcd_data(0x48);
    lcd_cmd(0xD31A); lcd_data(0x02);
    lcd_cmd(0xD31B); lcd_data(0x4A);
    lcd_cmd(0xD31C); lcd_data(0x02);
    lcd_cmd(0xD31D); lcd_data(0x7E);
    lcd_cmd(0xD31E); lcd_data(0x02);
    lcd_cmd(0xD31F); lcd_data(0xBC);
    lcd_cmd(0xD320); lcd_data(0x02);
    lcd_cmd(0xD321); lcd_data(0xE1);
    lcd_cmd(0xD322); lcd_data(0x03);
    lcd_cmd(0xD323); lcd_data(0x10);
    lcd_cmd(0xD324); lcd_data(0x03);
    lcd_cmd(0xD325); lcd_data(0x31);
    lcd_cmd(0xD326); lcd_data(0x03);
    lcd_cmd(0xD327); lcd_data(0x5A);
    lcd_cmd(0xD328); lcd_data(0x03);
    lcd_cmd(0xD329); lcd_data(0x73);
    lcd_cmd(0xD32A); lcd_data(0x03);
    lcd_cmd(0xD32B); lcd_data(0x94);
    lcd_cmd(0xD32C); lcd_data(0x03);
    lcd_cmd(0xD32D); lcd_data(0x9F);
    lcd_cmd(0xD32E); lcd_data(0x03);
    lcd_cmd(0xD32F); lcd_data(0xB3);
    lcd_cmd(0xD330); lcd_data(0x03);
    lcd_cmd(0xD331); lcd_data(0xB9);
    lcd_cmd(0xD332); lcd_data(0x03);
    lcd_cmd(0xD333); lcd_data(0xC1);
    lcd_cmd(0xD400); lcd_data(0x00);
    lcd_cmd(0xD401); lcd_data(0x37);
    lcd_cmd(0xD402); lcd_data(0x00);
    lcd_cmd(0xD403); lcd_data(0x52);
    lcd_cmd(0xD404); lcd_data(0x00);
    lcd_cmd(0xD405); lcd_data(0x7B);
    lcd_cmd(0xD406); lcd_data(0x00);
    lcd_cmd(0xD407); lcd_data(0x99);
    lcd_cmd(0xD408); lcd_data(0x00);
    lcd_cmd(0xD409); lcd_data(0xB1);
    lcd_cmd(0xD40A); lcd_data(0x00);
    lcd_cmd(0xD40B); lcd_data(0xD2);
    lcd_cmd(0xD40C); lcd_data(0x00);
    lcd_cmd(0xD40D); lcd_data(0xF6);
    lcd_cmd(0xD40E); lcd_data(0x01);
    lcd_cmd(0xD40F); lcd_data(0x27);
    lcd_cmd(0xD410); lcd_data(0x01);
    lcd_cmd(0xD411); lcd_data(0x4E);
    lcd_cmd(0xD412); lcd_data(0x01);
    lcd_cmd(0xD413); lcd_data(0x8C);
    lcd_cmd(0xD414); lcd_data(0x01);
    lcd_cmd(0xD415); lcd_data(0xBE);
    lcd_cmd(0xD416); lcd_data(0x02);
    lcd_cmd(0xD417); lcd_data(0x0B);
    lcd_cmd(0xD418); lcd_data(0x02);
    lcd_cmd(0xD419); lcd_data(0x48);
    lcd_cmd(0xD41A); lcd_data(0x02);
    lcd_cmd(0xD41B); lcd_data(0x4A);
    lcd_cmd(0xD41C); lcd_data(0x02);
    lcd_cmd(0xD41D); lcd_data(0x7E);
    lcd_cmd(0xD41E); lcd_data(0x02);
    lcd_cmd(0xD41F); lcd_data(0xBC);
    lcd_cmd(0xD420); lcd_data(0x02);
    lcd_cmd(0xD421); lcd_data(0xE1);
    lcd_cmd(0xD422); lcd_data(0x03);
    lcd_cmd(0xD423); lcd_data(0x10);
    lcd_cmd(0xD424); lcd_data(0x03);
    lcd_cmd(0xD425); lcd_data(0x31);
    lcd_cmd(0xD426); lcd_data(0x03);
    lcd_cmd(0xD427); lcd_data(0x5A);
    lcd_cmd(0xD428); lcd_data(0x03);
    lcd_cmd(0xD429); lcd_data(0x73);
    lcd_cmd(0xD42A); lcd_data(0x03);
    lcd_cmd(0xD42B); lcd_data(0x94);
    lcd_cmd(0xD42C); lcd_data(0x03);
    lcd_cmd(0xD42D); lcd_data(0x9F);
    lcd_cmd(0xD42E); lcd_data(0x03);
    lcd_cmd(0xD42F); lcd_data(0xB3);
    lcd_cmd(0xD430); lcd_data(0x03);
    lcd_cmd(0xD431); lcd_data(0xB9);
    lcd_cmd(0xD432); lcd_data(0x03);
    lcd_cmd(0xD433); lcd_data(0xC1);
    lcd_cmd(0xD500); lcd_data(0x00);
    lcd_cmd(0xD501); lcd_data(0x37);
    lcd_cmd(0xD502); lcd_data(0x00);
    lcd_cmd(0xD503); lcd_data(0x52);
    lcd_cmd(0xD504); lcd_data(0x00);
    lcd_cmd(0xD505); lcd_data(0x7B);
    lcd_cmd(0xD506); lcd_data(0x00);
    lcd_cmd(0xD507); lcd_data(0x99);
    lcd_cmd(0xD508); lcd_data(0x00);
    lcd_cmd(0xD509); lcd_data(0xB1);
    lcd_cmd(0xD50A); lcd_data(0x00);
    lcd_cmd(0xD50B); lcd_data(0xD2);
    lcd_cmd(0xD50C); lcd_data(0x00);
    lcd_cmd(0xD50D); lcd_data(0xF6);
    lcd_cmd(0xD50E); lcd_data(0x01);
    lcd_cmd(0xD50F); lcd_data(0x27);
    lcd_cmd(0xD510); lcd_data(0x01);
    lcd_cmd(0xD511); lcd_data(0x4E);
    lcd_cmd(0xD512); lcd_data(0x01);
    lcd_cmd(0xD513); lcd_data(0x8C);
    lcd_cmd(0xD514); lcd_data(0x01);
    lcd_cmd(0xD515); lcd_data(0xBE);
    lcd_cmd(0xD516); lcd_data(0x02);
    lcd_cmd(0xD517); lcd_data(0x0B);
    lcd_cmd(0xD518); lcd_data(0x02);
    lcd_cmd(0xD519); lcd_data(0x48);
    lcd_cmd(0xD51A); lcd_data(0x02);
    lcd_cmd(0xD51B); lcd_data(0x4A);
    lcd_cmd(0xD51C); lcd_data(0x02);
    lcd_cmd(0xD51D); lcd_data(0x7E);
    lcd_cmd(0xD51E); lcd_data(0x02);
    lcd_cmd(0xD51F); lcd_data(0xBC);
    lcd_cmd(0xD520); lcd_data(0x02);
    lcd_cmd(0xD521); lcd_data(0xE1);
    lcd_cmd(0xD522); lcd_data(0x03);
    lcd_cmd(0xD523); lcd_data(0x10);
    lcd_cmd(0xD524); lcd_data(0x03);
    lcd_cmd(0xD525); lcd_data(0x31);
    lcd_cmd(0xD526); lcd_data(0x03);
    lcd_cmd(0xD527); lcd_data(0x5A);
    lcd_cmd(0xD528); lcd_data(0x03);
    lcd_cmd(0xD529); lcd_data(0x73);
    lcd_cmd(0xD52A); lcd_data(0x03);
    lcd_cmd(0xD52B); lcd_data(0x94);
    lcd_cmd(0xD52C); lcd_data(0x03);
    lcd_cmd(0xD52D); lcd_data(0x9F);
    lcd_cmd(0xD52E); lcd_data(0x03);
    lcd_cmd(0xD52F); lcd_data(0xB3);
    lcd_cmd(0xD530); lcd_data(0x03);
    lcd_cmd(0xD531); lcd_data(0xB9);
    lcd_cmd(0xD532); lcd_data(0x03);
    lcd_cmd(0xD533); lcd_data(0xC1);
    lcd_cmd(0xD600); lcd_data(0x00);
    lcd_cmd(0xD601); lcd_data(0x37);
    lcd_cmd(0xD602); lcd_data(0x00);
    lcd_cmd(0xD603); lcd_data(0x52);
    lcd_cmd(0xD604); lcd_data(0x00);
    lcd_cmd(0xD605); lcd_data(0x7B);
    lcd_cmd(0xD606); lcd_data(0x00);
    lcd_cmd(0xD607); lcd_data(0x99);
    lcd_cmd(0xD608); lcd_data(0x00);
    lcd_cmd(0xD609); lcd_data(0xB1);
    lcd_cmd(0xD60A); lcd_data(0x00);
    lcd_cmd(0xD60B); lcd_data(0xD2);
    lcd_cmd(0xD60C); lcd_data(0x00);
    lcd_cmd(0xD60D); lcd_data(0xF6);
    lcd_cmd(0xD60E); lcd_data(0x01);
    lcd_cmd(0xD60F); lcd_data(0x27);
    lcd_cmd(0xD610); lcd_data(0x01);
    lcd_cmd(0xD611); lcd_data(0x4E);
    lcd_cmd(0xD612); lcd_data(0x01);
    lcd_cmd(0xD613); lcd_data(0x8C);
    lcd_cmd(0xD614); lcd_data(0x01);
    lcd_cmd(0xD615); lcd_data(0xBE);
    lcd_cmd(0xD616); lcd_data(0x02);
    lcd_cmd(0xD617); lcd_data(0x0B);
    lcd_cmd(0xD618); lcd_data(0x02);
    lcd_cmd(0xD619); lcd_data(0x48);
    lcd_cmd(0xD61A); lcd_data(0x02);
    lcd_cmd(0xD61B); lcd_data(0x4A);
    lcd_cmd(0xD61C); lcd_data(0x02);
    lcd_cmd(0xD61D); lcd_data(0x7E);
    lcd_cmd(0xD61E); lcd_data(0x02);
    lcd_cmd(0xD61F); lcd_data(0xBC);
    lcd_cmd(0xD620); lcd_data(0x02);
    lcd_cmd(0xD621); lcd_data(0xE1);
    lcd_cmd(0xD622); lcd_data(0x03);
    lcd_cmd(0xD623); lcd_data(0x10);
    lcd_cmd(0xD624); lcd_data(0x03);
    lcd_cmd(0xD625); lcd_data(0x31);
    lcd_cmd(0xD626); lcd_data(0x03);
    lcd_cmd(0xD627); lcd_data(0x5A);
    lcd_cmd(0xD628); lcd_data(0x03);
    lcd_cmd(0xD629); lcd_data(0x73);
    lcd_cmd(0xD62A); lcd_data(0x03);
    lcd_cmd(0xD62B); lcd_data(0x94);
    lcd_cmd(0xD62C); lcd_data(0x03);
    lcd_cmd(0xD62D); lcd_data(0x9F);
    lcd_cmd(0xD62E); lcd_data(0x03);
    lcd_cmd(0xD62F); lcd_data(0xB3);
    lcd_cmd(0xD630); lcd_data(0x03);
    lcd_cmd(0xD631); lcd_data(0xB9);
    lcd_cmd(0xD632); lcd_data(0x03);
    lcd_cmd(0xD633); lcd_data(0xC1);
    lcd_cmd(0xF000); lcd_data(0x55);
    lcd_cmd(0xF001); lcd_data(0xAA);
    lcd_cmd(0xF002); lcd_data(0x52);
    lcd_cmd(0xF003); lcd_data(0x08);
    lcd_cmd(0xF004); lcd_data(0x00);
    lcd_cmd(0xB000); lcd_data(0x08);
    lcd_cmd(0xB001); lcd_data(0x05);
    lcd_cmd(0xB002); lcd_data(0x02);
    lcd_cmd(0xB003); lcd_data(0x05);
    lcd_cmd(0xB004); lcd_data(0x02);
    lcd_cmd(0xB600); lcd_data(0x08);
    lcd_cmd(0xB500); lcd_data(0x50);
    lcd_cmd(0xB700); lcd_data(0x00);
    lcd_cmd(0xB701); lcd_data(0x00);
    lcd_cmd(0xB800); lcd_data(0x01);
    lcd_cmd(0xB801); lcd_data(0x05);
    lcd_cmd(0xB802); lcd_data(0x05);
    lcd_cmd(0xB803); lcd_data(0x05);
    lcd_cmd(0xBC00); lcd_data(0x00);
    lcd_cmd(0xBC01); lcd_data(0x00);
    lcd_cmd(0xBC02); lcd_data(0x00);
    lcd_cmd(0xCC00); lcd_data(0x03);
    lcd_cmd(0xCC01); lcd_data(0x00);
    lcd_cmd(0xCC02); lcd_data(0x00);
    lcd_cmd(0xBD00); lcd_data(0x01);
    lcd_cmd(0xBD01); lcd_data(0x84);
    lcd_cmd(0xBD02); lcd_data(0x07);
    lcd_cmd(0xBD03); lcd_data(0x31);
    lcd_cmd(0xBD04); lcd_data(0x00);
    lcd_cmd(0xBA00); lcd_data(0x01);
    lcd_cmd(0xFF00); lcd_data(0xAA);
    lcd_cmd(0xFF01); lcd_data(0x55);
    lcd_cmd(0xFF02); lcd_data(0x25);
    lcd_cmd(0xFF03); lcd_data(0x01);
}

static void lcd_set_window(uint16_t x0, uint16_t y0, uint16_t x1, uint16_t y1) {
    lcd_cmd(0x2A00); lcd_data(x0 >> 8);
    lcd_cmd(0x2A01); lcd_data(x0 & 0xFF);
    lcd_cmd(0x2A02); lcd_data(x1 >> 8);
    lcd_cmd(0x2A03); lcd_data(x1 & 0xFF);
    lcd_cmd(0x2B00); lcd_data(y0 >> 8);
    lcd_cmd(0x2B01); lcd_data(y0 & 0xFF);
    lcd_cmd(0x2B02); lcd_data(y1 >> 8);
    lcd_cmd(0x2B03); lcd_data(y1 & 0xFF);
    lcd_cmd(0x2C00); // RAMWR: subsequent lcd_data() calls stream pixels
}

void lcd_fill_rect(uint16_t x, uint16_t y, uint16_t w, uint16_t h, uint16_t color) {
    lcd_set_window(x, y, x + w - 1, y + h - 1);
    uint32_t n = (uint32_t)w * h;
    for (uint32_t i = 0; i < n; i++) {
        lcd_data(color);
    }
}

void lcd_fill(uint16_t color) {
    lcd_fill_rect(0, 0, NT35510_WIDTH, NT35510_HEIGHT, color);
}

void lcd_init(void) {
    for (int pin = READER_LCD_PIN_D0; pin < READER_LCD_PIN_D0 + 16; pin++) {
        gpio_init(pin);
        gpio_set_dir(pin, GPIO_OUT);
    }
    gpio_init(READER_LCD_PIN_CS);  gpio_set_dir(READER_LCD_PIN_CS, GPIO_OUT);  gpio_put(READER_LCD_PIN_CS, 0);
    gpio_init(READER_LCD_PIN_DC);  gpio_set_dir(READER_LCD_PIN_DC, GPIO_OUT);  gpio_put(READER_LCD_PIN_DC, 1);
    gpio_init(READER_LCD_PIN_WR);  gpio_set_dir(READER_LCD_PIN_WR, GPIO_OUT);  gpio_put(READER_LCD_PIN_WR, 1);
    gpio_init(READER_LCD_PIN_RST); gpio_set_dir(READER_LCD_PIN_RST, GPIO_OUT); gpio_put(READER_LCD_PIN_RST, 1);

    // Plain digital "on" for now -- proper PWM brightness via GPIO35/TPS61165
    // CTRL is a later step, this just needs light coming through the panel.
    gpio_init(READER_LCD_BL_PWM_PIN);
    gpio_set_dir(READER_LCD_BL_PWM_PIN, GPIO_OUT);
    gpio_put(READER_LCD_BL_PWM_PIN, 1);

    lcd_hw_reset();
    lcd_init_extra();

    lcd_cmd(0x3A00); lcd_data(0x55); // 16bpp pixel format
    lcd_cmd(0x1100); sleep_ms(120);  // sleep out
    lcd_cmd(0x2900);                 // display on
}
