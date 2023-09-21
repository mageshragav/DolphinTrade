from django.db import models

# Create your models here.

DIRECTION_STATUS = (
    (1,'up'),
    (2,'down')
)
RECOMMENDED = (
    (1, 'BUY'),
    (2, 'SELL'),
    (3, 'NEUTRAL')
)

class OlympTrade(models.Model):
    asset = models.CharField(max_length=250,default=None,blank=True,null=True)
    personal_recommend = models.JSONField(default=None,null=True)
    recommend = models.IntegerField(choices=RECOMMENDED,blank=True,null=True)
    recommend_buy = models.IntegerField(default=0,blank=True,null=True)
    recommend_sell = models.IntegerField(default=0,blank=True,null=True)
    recommend_neutral = models.IntegerField(default=0,blank=True,null=True)
    price = models.IntegerField(default=1,blank=True,null=True)
    timing = models.IntegerField(default=60,blank=True,null=True)
    direction = models.CharField(max_length=250,choices=DIRECTION_STATUS,default=None,null=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(default=None,null=True)

    class Meta:
        indexes = [
            models.Index(fields=['asset', 'created_at']),  # Composite index
            models.Index(fields=['asset']),  # Single-field index
        ]


class MovingAvg(models.Model):
    olymptrade = models.ForeignKey(OlympTrade,related_name='moving_olymp_trade',on_delete=models.CASCADE)
    recommend = models.IntegerField(choices=RECOMMENDED,blank=True,null=True)
    recommend_buy = models.IntegerField(default=0,blank=True,null=True)
    recommend_sell = models.IntegerField(default=0,blank=True,null=True)
    all_mvavg = models.JSONField(default=None,null=True)
    created_at = models.DateTimeField(auto_now=True)

class Indicators(models.Model):
    olymptrade = models.ForeignKey(OlympTrade,related_name='indicator_olymp_trade',on_delete=models.CASCADE)
    open = models.FloatField(default=0.0)
    close = models.FloatField(default=0.0)
    low = models.FloatField(default=0.0)
    high = models.FloatField(default=0.0)
    indictors = models.JSONField()
    created_at = models.DateTimeField(auto_now=True)