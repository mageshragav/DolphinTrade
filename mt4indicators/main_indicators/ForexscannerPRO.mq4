
#property copyright "FREE EA, Indicators > ForexCracked.com"
#property link      "http://www.forexscanners.com"

#property indicator_chart_window
#property indicator_buffers 2
#property indicator_color1 Green
#property indicator_color2 Red

string Gs_unused_76 = "Last Modified: 2011.06.26 18:45";
double G_ibuf_84[];
double G_ibuf_88[];
extern bool AlertOn = TRUE;
int Gi_unused_96 = 0;
double Gd_100 = 0.0;
double Gd_108 = 0.0;
double Gd_116 = 0.0;
double Gd_124 = 0.0;
double Gd_132 = 0.0;
double Gd_140 = 0.0;
double Gd_148 = 0.0;
double Gd_156 = 0.0;
double G_point_164 = 0.0001;
int Gi_unused_172 = -1;
int G_period_176 = 200;
double Gd_unused_180 = 0.15;
int Gi_188 = 2;
int Gi_192 = 0;
int Gi_196 = 7;
int Gi_unused_200 = 5000;
int G_bars_204 = 0;
int G_bars_208 = 0;
int G_bars_212 = 0;
int G_bars_216 = 0;
int Gi_220 = 500;

// E37F0136AA3FFAF149B351F6A4C948E9
int init() {
   SetIndexStyle(0, DRAW_ARROW);
   SetIndexStyle(1, DRAW_ARROW);
   SetIndexLabel(0, "BUY");
   SetIndexLabel(1, "SELL");
   SetIndexBuffer(0, G_ibuf_88);
   SetIndexBuffer(1, G_ibuf_84);
   SetIndexArrow(1, 234);
   SetIndexArrow(0, 233);
   if (Point == 0.00001) G_point_164 = 0.0001;
   else {
      if (Point == 0.001) G_point_164 = 0.01;
      else G_point_164 = Point;
   }
   f0_5();
   return (0);
}

// 52D46093050F38C27267BCE42543EF60
int deinit() {
   f0_17();
   f0_16();
   f0_15();
   return (0);
}

// EA2B2676C28C0DB26D39331A336C6B92
int start() {
   int Li_0;
   string Ls_4;
   bool Li_12 = FALSE;
   double Ld_16 = 0;
   Li_12 = f0_4(0, Ld_16);
   if (Li_12 == TRUE) {
      f0_17();
      f0_12();
   }
   if (Li_12 == 2) {
      f0_17();
      f0_0();
   }
   if (Li_12 == FALSE) {
      f0_17();
      f0_16();
   }
   f0_9();
   f0_5();
   int Li_unused_24 = 0;
   for (int Li_28 = 5000; Li_28 >= 1; Li_28--) {
      Li_0 = f0_8(Li_28);
      G_ibuf_88[Li_28] = 0;
      G_ibuf_84[Li_28] = 0;
      if (Li_0 == 1) G_ibuf_88[Li_28] = Low[Li_28] - 5.0 * G_point_164;
      if (Li_0 == 2) G_ibuf_84[Li_28] = High[Li_28] + 5.0 * G_point_164;
   }
   if (AlertOn) {
      Ls_4 = "";
      if (G_ibuf_88[1] > 0.0 && G_ibuf_88[2] == 0.0) {
         Ls_4 = "ForexScannerPRO" + " " + Symbol() + " " + Period() + " Min -  Green Arrow UP - Possible Buy Entry";
         f0_3(Ls_4, 1);
      }
      if (G_ibuf_84[1] > 0.0 && G_ibuf_84[2] == 0.0) {
         Ls_4 = "ForexScannerPRO" + " " + Symbol() + " " + Period() + " Min -  Red Arrow DOWN - Possible Sell Entry";
         f0_3(Ls_4, 2);
      }
   }
   return (0);
}

// 6ABA3523C7A75AAEA41CC0DEC7953CC5
int f0_8(int Ai_0) {
   double ima_4 = 0;
   double ima_12 = 0;
   double ima_20 = 0;
   double ima_28 = 0;
   ima_4 = iMA(NULL, 0, 4, 0, MODE_EMA, PRICE_CLOSE, Ai_0);
   ima_12 = iMA(NULL, 0, 8, 0, MODE_EMA, PRICE_CLOSE, Ai_0);
   ima_20 = iMA(NULL, 0, 4, 0, MODE_EMA, PRICE_CLOSE, Ai_0 + 1);
   ima_28 = iMA(NULL, 0, 8, 0, MODE_EMA, PRICE_CLOSE, Ai_0 + 1);
   double ima_36 = 0;
   double ima_44 = 0;
   double ima_52 = 0;
   ima_36 = iMA(NULL, 0, 50, 0, MODE_SMA, PRICE_CLOSE, Ai_0);
   ima_44 = iMA(NULL, 0, 21, 0, MODE_EMA, PRICE_CLOSE, Ai_0);
   ima_52 = iMA(NULL, 0, 10, 0, MODE_EMA, PRICE_CLOSE, Ai_0);
   if (ima_4 > ima_12 && ima_20 < ima_28 && ima_52 > ima_44 && ima_44 > ima_36) return (1);
   if (ima_4 < ima_12 && ima_20 > ima_28 && ima_36 > ima_44 && ima_44 > ima_52) return (2);
   return (0);
}

// 2FC9212C93C86A99B2C376C96453D3A4
int f0_3(string As_0, int Ai_8) {
   switch (Ai_8) {
   case 1:
      if (!((G_bars_204 == 0 || G_bars_204 < Bars))) break;
      Alert(As_0);
      G_bars_204 = Bars;
      return (1);
      break;
   case 2:
      if (!((G_bars_208 == 0 || G_bars_208 < Bars))) break;
      Alert(As_0);
      G_bars_208 = Bars;
      return (1);
      break;
   case 3:
      if (!((G_bars_212 == 0 || G_bars_212 < Bars))) break;
      Alert(As_0);
      G_bars_212 = Bars;
      return (1);
      break;
   case 4:
      if (!((G_bars_216 == 0 || G_bars_216 < Bars))) break;
      Alert(As_0);
      G_bars_216 = Bars;
      return (1);
      break;
   }
   return (0);
}

// 5710F6E623305B2C1458238C9757193B
void f0_5() {
   double Gda_0[1][6];
   double Ld_4;
   double Ld_12;
   double Ld_20;
   ArrayCopyRates(Gda_0, Symbol(), PERIOD_D1);
   if (DayOfWeek() == 1) {
      if (TimeDayOfWeek(iTime(Symbol(), PERIOD_D1, 1)) == 5) {
         Ld_4 = Gda_0[1][4];
         Ld_12 = Gda_0[1][3];
         Ld_20 = Gda_0[1][2];
      } else {
         for (int Li_28 = 5; Li_28 >= 0; Li_28--) {
            if (TimeDayOfWeek(iTime(Symbol(), PERIOD_D1, Li_28)) == 5) {
               Ld_4 = Gda_0[Li_28][4];
               Ld_12 = Gda_0[Li_28][3];
               Ld_20 = Gda_0[Li_28][2];
            }
         }
      }
   } else {
      Ld_4 = Gda_0[1][4];
      Ld_12 = Gda_0[1][3];
      Ld_20 = Gda_0[1][2];
   }
   Gd_100 = Ld_12 - Ld_20;
   Gd_108 = (Ld_12 + Ld_20 + Ld_4) / 3.0;
   Gd_116 = Ld_12 + 2.0 * (Gd_108 - Ld_20);
   Gd_124 = Gd_108 + (2.0 * Gd_108 - Ld_20 - (2.0 * Gd_108 - Ld_12));
   Gd_132 = 2.0 * Gd_108 - Ld_20;
   Gd_140 = 2.0 * Gd_108 - Ld_12;
   Gd_148 = Gd_108 - (2.0 * Gd_108 - Ld_20 - (2.0 * Gd_108 - Ld_12));
   Gd_156 = Ld_20 - 2.0 * (Ld_12 - Gd_108);
   f0_6(Gd_116, "R3", DarkGreen, 0, 0);
   f0_10("Resistance 3", Gd_116, DarkGreen);
   f0_6(Gd_124, "R2", DarkGreen, 0, 0);
   f0_10("Resistance 2", Gd_124, DarkGreen);
   f0_6(Gd_132, "R1", DarkGreen, 0, 0);
   f0_10("Resistance 1", Gd_132, DarkGreen);
   f0_6(Gd_108, "PIVIOT", DimGray, 1, 1);
   f0_10("Piviot level", Gd_108, DimGray);
   f0_6(Gd_140, "S1", Maroon, 0, 0);
   f0_10("Support 1", Gd_140, Maroon);
   f0_6(Gd_148, "S2", Maroon, 0, 0);
   f0_10("Support 2", Gd_148, Maroon);
   f0_6(Gd_156, "S3", Maroon, 0, 0);
   f0_10("Support 3", Gd_156, Maroon);
}

// 945D754CB0DC06D04243FCBA25FC0802
void f0_10(string A_name_0, double A_price_8, color A_color_16) {
   if (ObjectFind(A_name_0) != 0) {
      ObjectCreate(A_name_0, OBJ_TEXT, 0, Time[10], A_price_8);
      ObjectSetText(A_name_0, A_name_0, 8, "Arial", CLR_NONE);
      ObjectSet(A_name_0, OBJPROP_COLOR, A_color_16);
      return;
   }
   ObjectMove(A_name_0, 0, Time[10], A_price_8);
}

// 58B0897F29A3AD862616D6CBF39536ED
void f0_6(double A_price_0, string A_name_8, color A_color_16, int Ai_20, int A_width_24) {
   if (ObjectFind(A_name_8) == -1) {
      ObjectCreate(A_name_8, OBJ_HLINE, 0, Time[0], A_price_0, Time[0], A_price_0);
      if (Ai_20 == 1) ObjectSet(A_name_8, OBJPROP_STYLE, STYLE_SOLID);
      else ObjectSet(A_name_8, OBJPROP_STYLE, STYLE_DOT);
      ObjectSet(A_name_8, OBJPROP_COLOR, A_color_16);
      ObjectSet(A_name_8, OBJPROP_WIDTH, A_width_24);
   } else {
      ObjectDelete(A_name_8);
      ObjectCreate(A_name_8, OBJ_HLINE, 0, Time[0], A_price_0, Time[0], A_price_0);
      if (Ai_20 == 1) ObjectSet(A_name_8, OBJPROP_STYLE, STYLE_SOLID);
      else ObjectSet(A_name_8, OBJPROP_STYLE, STYLE_DOT);
      ObjectSet(A_name_8, OBJPROP_COLOR, A_color_16);
      ObjectSet(A_name_8, OBJPROP_WIDTH, A_width_24);
   }
   WindowRedraw();
}

// 9B1AEE847CFB597942D106A4135D4FE6
void f0_11(int Ai_0, int Ai_4, string A_text_8, int A_fontsize_16 = 10, color A_color_20 = 65535, int Ai_24 = 5, int A_y_28 = 20, int Ai_32 = 80, int Ai_36 = 15) {
   bool Li_40 = FALSE;
   string Ls_44 = "CPrint_Line" + Ai_0 + "_" + Ai_4;
   for (int objs_total_52 = ObjectsTotal(); objs_total_52 >= 0; objs_total_52--)
      if (StringFind(ObjectName(objs_total_52), Ls_44, 0) > -1) Li_40 = TRUE;
   if (Li_40) {
      ObjectSetText(Ls_44, A_text_8, A_fontsize_16, "Arial Bold", A_color_20);
      WindowRedraw();
      return;
   }
   ObjectCreate(Ls_44, OBJ_LABEL, 0, 0, 0);
   ObjectSetText(Ls_44, A_text_8, A_fontsize_16, "Arial Bold", A_color_20);
   ObjectSet(Ls_44, OBJPROP_XDISTANCE, Ai_24 + (Ai_4 - 1) * Ai_32);
   if (Ai_0 == 1) {
      ObjectSet(Ls_44, OBJPROP_YDISTANCE, A_y_28);
      return;
   }
   ObjectSet(Ls_44, OBJPROP_YDISTANCE, A_y_28 + Ai_36 * (Ai_0 - 1));
}

// D362D41CFF235C066CFB390D52F4EB13
void f0_15() {
   ObjectDelete("S1");
   ObjectDelete("S2");
   ObjectDelete("S3");
   ObjectDelete("R1");
   ObjectDelete("R2");
   ObjectDelete("R3");
   ObjectDelete("PIVIOT");
   ObjectDelete("Support 1");
   ObjectDelete("Support 2");
   ObjectDelete("Support 3");
   ObjectDelete("Piviot level");
   ObjectDelete("Resistance 1");
   ObjectDelete("Resistance 2");
   ObjectDelete("Resistance 3");
}

// A9B24A824F70CC1232D1C2BA27039E8D
void f0_12() {
   f0_11(2, 1, "Analyze Trend = ", 18, Green, 5, 10);
   f0_14(1, 190, 8, 20, ".", 32768);
}

// 09CBB5F5CE12C31A043D5C81BF20AA4A
void f0_0() {
   f0_11(2, 1, "Analyze Trend = ", 18, Red, 5, 10);
   f0_14(2, 190, 5, 20, ".", 255);
}

// F7B1F0AA13347699EFAE0D924298CB02
void f0_16() {
   f0_11(2, 1, "Analyze Trend = ", 18, White, 5, 10);
   f0_11(2, 3, "---", 18, Silver, 5, 10, 105);
}

// 78BAA8FAE18F93570467778F2E829047
void f0_9() {
   int Li_unused_0 = 33924;
   f0_13(3, 1, "Average Daily Range: " + f0_1() + " pips", 10, White, 5, 25);
   f0_13(5, 1, "ForexScanner PRO", 8, White, 5, 25);
   f0_13(6, 1, "http://www.forexscanners.com", 8, White, 5, 25);
}

// AA5EA51BFAC7B64E723BF276E0075513
void f0_13(int Ai_0, int Ai_4, string A_text_8, int A_fontsize_16 = 10, color A_color_20 = 65535, int Ai_24 = 5, int A_y_28 = 20, int Ai_32 = 80, int Ai_36 = 15) {
   bool Li_40 = FALSE;
   string Ls_44 = "CPrint_Line" + Ai_0 + "_" + Ai_4;
   for (int objs_total_52 = ObjectsTotal(); objs_total_52 >= 0; objs_total_52--)
      if (StringFind(ObjectName(objs_total_52), Ls_44, 0) > -1) Li_40 = TRUE;
   if (Li_40) {
      ObjectSetText(Ls_44, A_text_8, A_fontsize_16, "Arial", A_color_20);
      WindowRedraw();
      return;
   }
   ObjectCreate(Ls_44, OBJ_LABEL, 0, 0, 0);
   ObjectSetText(Ls_44, A_text_8, A_fontsize_16, "Arial", A_color_20);
   ObjectSet(Ls_44, OBJPROP_XDISTANCE, Ai_24 + (Ai_4 - 1) * Ai_32);
   if (Ai_0 == 1) {
      ObjectSet(Ls_44, OBJPROP_YDISTANCE, A_y_28);
      return;
   }
   ObjectSet(Ls_44, OBJPROP_YDISTANCE, A_y_28 + Ai_36 * (Ai_0 - 1));
}

// 2569208C5E61CB15E209FFE323DB48B7
int f0_1() {
   int Li_0 = 0;
   int Li_ret_4 = 0;
   RefreshRates();
   for (Li_0 = 1; Li_0 <= 10; Li_0++) {
      RefreshRates();
      Li_ret_4 = Li_ret_4 + (iHigh(NULL, PERIOD_D1, Li_0) - iLow(NULL, PERIOD_D1, Li_0)) / G_point_164;
   }
   Li_ret_4 /= 10;
   return (Li_ret_4);
}

// FD4055E1AC0A7D690C66D37B2C70E529
void f0_17() {
   string name_0;
   int objs_total_8 = ObjectsTotal();
   for (int Li_12 = ObjectsTotal() - 1; Li_12 >= 0; Li_12--) {
      name_0 = ObjectName(Li_12);
      if (StringFind(name_0, "CPrint_", 0) > -1) ObjectDelete(name_0);
      if (StringFind(name_0, "L_", 0) > -1) ObjectDelete(name_0);
      WindowRedraw();
   }
}

// D1DDCE31F1A86B3140880F6B1877CBF8
void f0_14(int Ai_0 = 0, int Ai_4 = 5, int Ai_8 = 5, int Ai_12 = 20, string As_16 = ".", int Ai_24 = 16711680) {
   if (Ai_0 == 1) {
      f0_2("A_" + Gi_220, Ai_4, Ai_8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 1, Ai_8 + 2, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 1, Ai_8 + 2, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 4, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 4, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 4, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 3, Ai_8 + 6, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 6, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 6, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 6, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 3, Ai_8 + 6, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 4, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 3, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 3, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4 + 4, Ai_8 + 8, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 10, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 12, As_16, Ai_12, Ai_24);
      Gi_220++;
      f0_2("A_" + Gi_220, Ai_4, Ai_8 + 14, As_16, Ai_12, Ai_24);
      Gi_220++;
      return;
   }
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 4, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 6, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 8, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 4, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 3, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 3, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 4, Ai_8 + 10, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 3, Ai_8 + 12, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 12, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 12, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 12, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 3, Ai_8 + 12, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 2, Ai_8 + 14, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 14, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 2, Ai_8 + 14, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 - 1, Ai_8 + 16, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4 + 1, Ai_8 + 16, As_16, Ai_12, Ai_24);
   Gi_220++;
   f0_2("A_" + Gi_220, Ai_4, Ai_8 + 18, As_16, Ai_12, Ai_24);
   Gi_220++;
}

// 28EFB830D150E70A8BB0F12BAC76EF35
void f0_2(string As_0, int A_x_8, int A_y_12, string A_text_16 = "-", int A_fontsize_24 = 42, color A_color_28 = 65535, string A_fontname_32 = "Arial") {
   ObjectCreate("L_" + As_0, OBJ_LABEL, 0, 0, 0);
   ObjectSet("L_" + As_0, OBJPROP_COLOR, A_color_28);
   ObjectSet("L_" + As_0, OBJPROP_XDISTANCE, A_x_8);
   ObjectSet("L_" + As_0, OBJPROP_YDISTANCE, A_y_12);
   ObjectSetText("L_" + As_0, A_text_16, A_fontsize_24, A_fontname_32, A_color_28);
   WindowRedraw();
}

// 50257C26C4E5E915F022247BABD914FE
int f0_4(int Ai_0, double &Ad_4) {
   bool Li_12 = TRUE;
   bool Li_16 = TRUE;
   for (int Li_20 = Ai_0; Li_20 <= Gi_196 + Ai_0; Li_20++) {
      if (f0_7(Li_20) >= 0.0) Li_16 = FALSE;
      if (f0_7(Li_20) <= 0.0) Li_12 = FALSE;
   }
   Ad_4 = f0_7(Ai_0);
   if (Li_12 == TRUE && Li_16 == FALSE) return (1);
   if (Li_12 == FALSE && Li_16 == TRUE) return (2);
   return (0);
}

// 689C35E4872BA754D7230B8ADAA28E48
double f0_7(int Ai_0) {
   if (Gi_192 >= Gi_188) {
      Print("Error: EndEMAShift >= StartEMAShift");
      Gi_188 = 6;
      Gi_192 = 0;
   }
   int Li_4 = IndicatorCounted();
   if (Li_4 < 0) return (-1);
   if (Li_4 > 0) Li_4--;
   int Li_8 = Bars - Li_4;
   double Ld_unused_12 = 0.0349065556;
   double Ld_20 = 10000.0;
   string Ls_28 = StringSubstr(Symbol(), 3, 3);
   if (Ls_28 == "JPY") Ld_20 = 100.0;
   int Li_36 = Gi_188 - Gi_192;
   Ld_20 /= Li_36;
   double ima_40 = iMA(NULL, 0, G_period_176, 0, MODE_SMA, PRICE_MEDIAN, Ai_0 + Gi_192);
   double ima_48 = iMA(NULL, 0, G_period_176, 0, MODE_SMA, PRICE_MEDIAN, Ai_0 + Gi_188);
   double Ld_ret_56 = Ld_20 * (ima_40 - ima_48) / 2.0;
   return (Ld_ret_56);
}