#property indicator_chart_window
#property indicator_buffers 2
#property indicator_color1 Lime
#property indicator_color2 Red

bool Gi_unused_76 = FALSE;
int Gi_unused_80 = 2008;
int Gi_unused_84 = 3;
int Gi_unused_88 = 75;
int Gi_unused_92 = 70;
int Gi_unused_96 = 77;
int Gi_unused_100 = 109;
int Gi_unused_104 = 52;
string Gs_dummy_108;
double Gd_unused_116 = 15.0;
double Gd_unused_124 = 45.0;
int Gi_unused_132 = 0;
int Gi_unused_136 = 21;
int Gi_unused_140 = 1;
int Gi_unused_144 = 6;
int Gi_unused_148 = -1;
int Gi_unused_152 = 240;
int Gi_unused_156 = -4;
double Gd_unused_160 = 0.3;
string Gs_dummy_168;
string Gs_dummy_176;
string Gs_dummy_184;
string Gs_dummy_192;
int Gi_216 = 0;
int Gi_220 = 17;
int Gi_224 = 3;
double Gd_228 = 25.0;
int Gi_236 = 159;
string Gs_240;
double Gd_248;
int G_bars_256 = 0;
bool Gi_260 = TRUE;
extern string Alert_Setting = "---------- Alert Setting";
extern bool EnableAlert = TRUE;
extern string SoundFilename = "alert.wav";
int Gi_284;
int Gi_288;
int Gi_292;
int Gi_296;
int G_count_300 = 0;
int G_count_304 = 0;
int Gi_unused_308 = 0;
int Gi_unused_312 = 0;
double Gd_316;
double G_high_324;
double G_low_332;
double G_ibuf_340[];
double G_ibuf_344[];
int Gi_unused_356 = 0;
int Gi_unused_360 = 0;
int Gi_unused_364 = 0;
int Gi_unused_368 = 0;
int Gi_unused_372 = 0;
double Gd_unused_376 = 0.0;
double Gd_unused_384 = 0.0;
double Gd_unused_392 = 0.0;
int Gi_unused_400 = 0;
int Gi_unused_420 = 0;
int Gi_unused_424 = 0;
int Gi_unused_428 = 50;
int Gi_unused_432 = 2;
int Gi_unused_436 = 100;
int Gi_unused_440 = 2;
int Gi_unused_444 = 200;
int Gi_unused_448 = 2;

// E37F0136AA3FFAF149B351F6A4C948E9
int init() {
   if (Bars < Gi_216 + Gd_228 || Gi_216 == 0) Gi_288 = Bars - Gd_228;
   else Gi_288 = Gi_216;
   IndicatorBuffers(2);
   IndicatorShortName("SHI_SilverTrendSig");
   SetIndexStyle(0, DRAW_ARROW, STYLE_SOLID, Gi_224);
   SetIndexStyle(1, DRAW_ARROW, STYLE_SOLID, Gi_224);
   SetIndexArrow(0, Gi_236);
   SetIndexArrow(1, Gi_236);
   SetIndexBuffer(0, G_ibuf_344);
   SetIndexBuffer(1, G_ibuf_340);
   SetIndexDrawBegin(0, Bars - Gi_288);
   SetIndexDrawBegin(1, Bars - Gi_288);
   ArrayInitialize(G_ibuf_340, 0.0);
   ArrayInitialize(G_ibuf_344, 0.0);
   return (0);
}

// 52D46093050F38C27267BCE42543EF60
int deinit() {
   return (0);
}

// B3AA0053540040F9E473EAD4D03C19A7
void f0_0() {
   string Ls_0 = "";
   int Li_unused_8 = 1;
   if (Digits < 4) Gd_248 = 0.01;
   else Gd_248 = 0.0001;
   if (G_bars_256 != Bars) G_bars_256 = Bars;
   double iatr_12 = iATR(Symbol(), Period(), 5, 1);
   double Ld_20 = 1.45 * MathRound(iatr_12 * MathPow(7, Digits));
   double Ld_28 = 2.0 * Ld_20;
   Ls_0 = Ls_0 
      + "\n  " 
      + "\n " 
      + "\n " 
      + "\n  .............................................. " 
      + "\n  Market Range = " + DoubleToStr(Ld_28, 0) + " Pips " 
      + "\n  Market Condition : " + Gs_240 + "" 
      + "\n  .............................................. " 
      + "\n  Broker Time Is " + TimeToStr(TimeCurrent()) + "" 
      + "\n  Account Curency:" + AccountCurrency() + "" 
      + "\n  Spread = " + DoubleToStr((Ask - Bid) / Gd_248, 1) + " pips" 
   + "\n  Leverage 1:" + AccountLeverage() + "";
   Comment(Ls_0);
   if (ObjectFind("LV") < 0) {
      ObjectCreate("LV", OBJ_LABEL, 0, 0, 0);
      ObjectSetText("LV", "Xtreme Binary Bot", 9, "Tahoma Bold", Black);
      ObjectSet("LV", OBJPROP_CORNER, 0);
      ObjectSet("LV", OBJPROP_BACK, FALSE);
      ObjectSet("LV", OBJPROP_XDISTANCE, 22);
      ObjectSet("LV", OBJPROP_YDISTANCE, 23);
   }
   if (ObjectFind("BKGR") < 0) {
      ObjectCreate("BKGR", OBJ_LABEL, 0, 0, 0);
      ObjectSetText("BKGR", "g", 110, "Webdings", White);
      ObjectSet("BKGR", OBJPROP_CORNER, 0);
      ObjectSet("BKGR", OBJPROP_BACK, TRUE);
      ObjectSet("BKGR", OBJPROP_XDISTANCE, 5);
      ObjectSet("BKGR", OBJPROP_YDISTANCE, 15);
   }
   if (ObjectFind("BKGR2") < 0) {
      ObjectCreate("BKGR2", OBJ_LABEL, 0, 0, 0);
      ObjectSetText("BKGR2", "g", 110, "Webdings", Gray);
      ObjectSet("BKGR2", OBJPROP_BACK, TRUE);
      ObjectSet("BKGR2", OBJPROP_XDISTANCE, 5);
      ObjectSet("BKGR2", OBJPROP_YDISTANCE, 60);
   }
   if (ObjectFind("BKGR3") < 0) {
      ObjectCreate("BKGR3", OBJ_LABEL, 0, 0, 0);
      ObjectSetText("BKGR3", "g", 110, "Webdings", Gray);
      ObjectSet("BKGR3", OBJPROP_CORNER, 0);
      ObjectSet("BKGR3", OBJPROP_BACK, TRUE);
      ObjectSet("BKGR3", OBJPROP_XDISTANCE, 5);
      ObjectSet("BKGR3", OBJPROP_YDISTANCE, 45);
   }
   if (ObjectFind("BKGR4") < 0) {
      ObjectCreate("BKGR4", OBJ_LABEL, 0, 0, 0);
      ObjectSetText("BKGR4", "g", 110, "Webdings", Gray);
      ObjectSet("BKGR4", OBJPROP_CORNER, 0);
      ObjectSet("BKGR4", OBJPROP_BACK, TRUE);
      ObjectSet("BKGR4", OBJPROP_XDISTANCE, 5);
      ObjectSet("BKGR4", OBJPROP_YDISTANCE, 84);
   }
}

// EA2B2676C28C0DB26D39331A336C6B92
int start() {
   string Ls_unused_84;
   string Ls_unused_92;
   string Ls_unused_100;
   double Lda_unused_120[];
   double Lda_unused_124[];
   double icci_168;
   double imomentum_176;
   double imomentum_184;
   double iwpr_192;
   double iforce_200;
   double ibands_208;
   double ibands_216;
   double ibands_224;
   double ima_232;
   double ima_240;
   double ima_248;
   double ibands_256;
   double ima_264;
   double ima_272;
   string Ls_280;
   int Li_unused_0 = 5;
   int Li_unused_4 = 53;
   int Li_unused_64 = 36;
   int Li_unused_68 = 20;
   int Li_unused_72 = 5;
   int Li_unused_76 = 0;
   int Li_unused_80 = 0;
   double istochastic_108 = iStochastic(NULL, 0, 20, 12, 12, MODE_EMA, 1, MODE_MAIN, 0);
   if (istochastic_108 <= 75.0 && istochastic_108 >= 25.0) Gs_240 = "SAFE TRADE";
   else {
      if (istochastic_108 > 75.0 && istochastic_108 <= 88.0) Gs_240 = "S/R AREA";
      else {
         if (istochastic_108 < 25.0 && istochastic_108 >= 12.0) Gs_240 = "S/R AREA";
         else {
            if (istochastic_108 > 88.0) Gs_240 = "HIGH RISK!";
            else
               if (istochastic_108 < 12.0) Gs_240 = "HIGH RISK!";
         }
      }
   }
   if (Gi_260) f0_0();
   int ind_counted_116 = IndicatorCounted();
   int Li_unused_128 = 10;
   int Li_unused_132 = 400;
   int Li_unused_136 = 1;
   int Li_unused_140 = 3;
   int Li_unused_144 = 380;
   int Li_unused_148 = 65535;
   int Li_unused_152 = 16777215;
   int Li_unused_164 = 5;
   if (ind_counted_116 < 0) return (-1);
   if (Gi_288 > Bars - ind_counted_116) Gi_288 = Bars - ind_counted_116;
   for (Gi_284 = 1; Gi_284 < Gi_288; Gi_284++) {
      Gd_316 = 0;
      for (Gi_292 = Gi_284; Gi_292 < Gi_284 + 10; Gi_292++) Gd_316 += (Gi_284 + 10 - Gi_292) * (High[Gi_292] - Low[Gi_292]);
      Gd_316 /= 55.0;
      G_high_324 = High[iHighest(NULL, 0, MODE_HIGH, Gd_228, Gi_284)];
      G_low_332 = Low[iLowest(NULL, 0, MODE_LOW, Gd_228, Gi_284)];
      HideTestIndicators(TRUE);
      icci_168 = iCCI(Symbol(), PERIOD_M1, 80, PRICE_CLOSE, 0);
      imomentum_176 = iMomentum(Symbol(), PERIOD_M1, 60, PRICE_CLOSE, 0);
      imomentum_184 = iMomentum(Symbol(), PERIOD_M5, 4, PRICE_CLOSE, 0);
      iwpr_192 = iWPR(Symbol(), PERIOD_M1, 14, 0);
      iforce_200 = iForce(Symbol(), PERIOD_M5, 13, MODE_SMA, PRICE_CLOSE, 0);
      ibands_208 = iBands(Symbol(), PERIOD_M5, 20, 2, 0, PRICE_WEIGHTED, MODE_UPPER, 1);
      ibands_216 = iBands(Symbol(), PERIOD_M5, 20, 2, 0, PRICE_WEIGHTED, MODE_BASE, 1);
      ibands_224 = iBands(Symbol(), PERIOD_M5, 20, 2, 0, PRICE_WEIGHTED, MODE_LOWER, 1);
      ima_232 = iMA(Symbol(), PERIOD_M5, 1, 0, MODE_EMA, PRICE_HIGH, 0);
      ima_240 = iMA(Symbol(), PERIOD_M5, 1, 0, MODE_EMA, PRICE_MEDIAN, 0);
      ima_248 = iMA(Symbol(), PERIOD_M5, 1, 0, MODE_EMA, PRICE_LOW, 0);
      ibands_256 = iBands(Symbol(), PERIOD_M5, 20, 2, 0, PRICE_WEIGHTED, MODE_UPPER, 0);
      ima_264 = iMA(Symbol(), PERIOD_M1, 1, 0, MODE_EMA, PRICE_MEDIAN, 0);
      ima_272 = iMA(Symbol(), PERIOD_M1, 1, 0, MODE_EMA, PRICE_LOW, 0);
      HideTestIndicators(FALSE);
      if (Close[Gi_284] > G_high_324 - (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != 1) {
         G_ibuf_340[Gi_284] = High[Gi_284] + Gd_316 / 2.0;
         if (Close[Gi_284] > G_high_324 - (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != 1) Gi_296 = 1;
         if (Close[Gi_284] > G_high_324 - (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != 1) G_count_304 = 0;
      } else {
         if (Close[Gi_284] < G_low_332 + (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != -1) {
            G_ibuf_344[Gi_284] = Low[Gi_284] - Gd_316 / 2.0;
            if (Close[Gi_284] < G_low_332 + (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != -1) Gi_296 = -1;
            if (Close[Gi_284] < G_low_332 + (G_high_324 - G_low_332) * Gi_220 / 100.0 && Gi_296 != -1) G_count_300 = 0;
         }
      }
   }
   if (EnableAlert) {
      if (Gi_296 == 1 && G_count_300 == 1) Alert(Symbol(), " - ", "BUY - UP DIRECTION !");
      if (Gi_296 == 1 && G_count_300 == 1) Alert(Ls_280);
      if (Gi_296 == 1 && G_count_300 == 1) PlaySound(SoundFilename);
      if (Gi_296 == 1 && G_count_300 == 1) G_count_300++;
      if (Gi_296 == -1 && G_count_304 == 1) Alert(Symbol(), " - ", "SELL - DOWN DIRECTION !");
      if (Gi_296 == -1 && G_count_304 == 1) Alert(Ls_280);
      if (Gi_296 == -1 && G_count_304 == 1) PlaySound(SoundFilename);
      if (Gi_296 == -1 && G_count_304 == 1) G_count_304++;
   }
   return (0);
}
