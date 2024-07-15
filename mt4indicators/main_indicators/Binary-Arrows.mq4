//+------------------------------------------------------------------+
//|                                                Binary arrows.mq4 |
//+------------------------------------------------------------------+
#property copyright "Copyright Lorenzo Alessio."
#property description "Binary Arows"

#property indicator_chart_window
#property indicator_buffers 2
#property indicator_color1 Red
#property indicator_width1 2
#property indicator_color2 DeepSkyBlue
#property indicator_width2 2

extern int SignalGap = 20;
extern int BarsToCount = 500;

int OneInitOnly=true;

int dist=24;
double b1[];
double b2[];

int init()  
  {
   SetIndexStyle(0,DRAW_ARROW,STYLE_SOLID,2);
   SetIndexArrow(0,234);
   SetIndexBuffer(0,b1);

   SetIndexStyle(1,DRAW_ARROW,STYLE_SOLID,2);
   SetIndexArrow(1,233);
   SetIndexBuffer(1,b2);

   if(OneInitOnly==true)
     {
      int i;
      OneInitOnly=false;
      for (i=BarsToCount;i>=0;i--)   
        {
         b1[i]=EMPTY_VALUE;
         b2[i]=EMPTY_VALUE;
        }
     }
  }

int start() {
   int k,i,j,limit,hhb,llb;
   
   for (i=BarsToCount;i>=0;i--)   
     {
      hhb = iHighest(Symbol(),0,MODE_HIGH,dist,i-dist/2);
      llb = iLowest(Symbol(),0,MODE_LOW,dist,i-dist/2);

      if (i==hhb) b1[i]=High[hhb]+SignalGap*Point;
      if (i==llb) b2[i]=Low[llb]-SignalGap*Point;
     }
  
}

