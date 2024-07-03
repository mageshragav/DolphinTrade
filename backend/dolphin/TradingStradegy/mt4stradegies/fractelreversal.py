import pandas as pd


class FractelReversal:

    def __init__(self,df: pd.DataFrame,assest:str) -> None:
        self.df = df.copy()
        # Initialize buffers
        self.df.loc[:,'BullishReversal'] = 0.0
        self.df.loc[:,'BearishReversal'] = 0.0
        self.assest = assest


    # Define functions for fractals
    def upper_fractal_7b(self, i):
        middle = self.df['high'][i + 3]
        v1 = self.df['high'][i]
        v2 = self.df['high'][i + 1]
        v3 = self.df['high'][i + 2]
        v5 = self.df['high'][i + 4]
        v6 = self.df['high'][i + 5]
        v7 = self.df['high'][i + 6]
        v1_c = self.df['low'][i]
        v7_c = self.df['low'][i + 5]
        
        if (middle > v1 and middle > v2 and middle > v3 and middle > v5 and middle > v6 and middle > v7) and v1_c < v7_c:
            return middle
        return None

    def lower_fractal_7b(self, i):
        middle = self.df['low'][i + 3]
        v1 = self.df['low'][i]
        v2 = self.df['low'][i + 1]
        v3 = self.df['low'][i + 2]
        v5 = self.df['low'][i + 4]
        v6 = self.df['low'][i + 5]
        v7 = self.df['low'][i + 6]
        v1_c = self.df['high'][i]
        v7_c = self.df['high'][i + 5]
        
        if (middle < v1 and middle < v2 and middle < v3 and middle < v5 and middle < v6 and middle < v7) and v1_c > v7_c:
            return middle
        return None

    def upper_fractal_5b(self, i):
        middle = self.df['high'][i + 2]
        v1 = self.df['high'][i]
        v2 = self.df['high'][i + 1]
        v3 = self.df['high'][i + 3]
        v4 = self.df['high'][i + 4]
        v1_c = self.df['low'][i]
        v4_c = self.df['low'][i + 3]
        
        if (middle > v1 and middle > v2 and middle > v3 and middle > v4) and v1_c < v4_c:
            return middle
        return None

    def lower_fractal_5b(self, i):
        middle = self.df['low'][i + 2]
        v1 = self.df['low'][i]
        v2 = self.df['low'][i + 1]
        v3 = self.df['low'][i + 3]
        v4 = self.df['low'][i + 4]
        v1_c = self.df['high'][i]
        v4_c = self.df['high'][i + 3]
        
        if (middle < v1 and middle < v2 and middle < v3 and middle < v4) and v1_c > v4_c:
            return middle
        return None
    
    def mainloop(self):
        # Iterate over the data to find signals
        last_signal = 0
        last_action = 'OP_BUY'

        for i in range(len(self.df) - 7):
            lower5 = self.lower_fractal_5b(i)
            lower7 = self.lower_fractal_7b(i)
            upper5 = self.upper_fractal_5b(i)
            upper7 = self.upper_fractal_7b(i)

            # Long 5-bar reversal
            if lower5 and lower5 != last_signal and last_action == 'OP_SELL':
                self.df.at[i + 2, 'BullishReversal'] = lower5
                last_signal = lower5
                last_action = 'OP_BUY'
            # Long 7-bar reversal
            elif lower7 and lower7 != last_signal and last_action == 'OP_SELL':
                self.df.at[i + 3, 'BullishReversal'] = lower7
                last_signal = lower7
                last_action = 'OP_BUY'
            # Short 5-bar reversal
            elif upper5 and upper5 != last_signal and last_action == 'OP_BUY':
                self.df.at[i + 2, 'BearishReversal'] = upper5
                last_signal = upper5
                last_action = 'OP_SELL'
            # Short 7-bar reversal
            elif upper7 and upper7 != last_signal and last_action == 'OP_BUY':
                self.df.at[i + 3, 'BearishReversal'] = upper7
                last_signal = upper7
                last_action = 'OP_SELL'
        self.df.to_csv(f'/tmp/bullish_{self.assest}.csv')
        return self.df
