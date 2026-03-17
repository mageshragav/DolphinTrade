import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
 
class BrowserInstance:
    def __init__(self,host,username,password) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.driver = uc.Chrome(headless=True) 

    def openurl(self,host):
        self.driver.get(host)
    
    def login(self):
        pass

    def get_session(self):
        pass
