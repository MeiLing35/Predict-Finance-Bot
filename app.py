import requests,json,time,os,pathlib,binascii,random,sys
from web3 import Web3
from eth_account.messages import encode_defunct
from eth_account import Account
import colorama
from colorama import Fore,Back,Style
colorama.init(autoreset=True)
class Config:
    AUTH_URL="https://api.prdt.finance"
    TOKEN_URL="https://tokenapi.prdt.finance"
    WALLETS_FILE="all_wallets.json"
    DEFAULT_REFERRAL_CODE="1234567890"
    DEFAULT_WALLET_COUNT=1
    DEFAULT_DELAY_BETWEEN_ACCOUNTS=5
    PROXY="USERNAME:PASSWORD@HOST:PORT"
    HEADERS={"Content-Type":"application/json","Accept":"application/json, text/plain, */*","Origin":"https://prdt.finance","Referer":"https://prdt.finance/"}
    USER_AGENT="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    @classmethod
    def get_headers(cls,with_user_agent=False):
        headers=cls.HEADERS.copy()
        if with_user_agent:headers["User-Agent"]=cls.USER_AGENT
        return headers
class PrdtAutomation:
    def __init__(self,private_key=None,wallet_address=None,referral_code=None,wallet_file=None,wallet_data=None,proxy=None):
        self.web3=Web3()
        self.wallet_file=wallet_file
        self.wallet_data=wallet_data
        if self.wallet_data:
            self.private_key=self.wallet_data['private_key']
            self.wallet_address=self.wallet_data['address']
        elif private_key is None or wallet_address is None:
            self.private_key,self.wallet_address=self._get_or_create_wallet()
        else:
            self.private_key=private_key if private_key.startswith('0x')else f'0x{private_key}'
            self.wallet_address=wallet_address.lower()
        self.referral_code=referral_code if referral_code else Config.DEFAULT_REFERRAL_CODE
        self.session=requests.Session()
        self.proxy=proxy
        if self.proxy:
            self.session.proxies={'http':f'http://{self.proxy}','https':f'http://{self.proxy}'}
            print(f"{Fore.CYAN}Using proxy: {self.proxy}")
        self.auth_url=Config.AUTH_URL
        self.token_url=Config.TOKEN_URL
        self.cookies={}
        print(f"{Fore.GREEN}Using wallet address: {Fore.YELLOW}{self.wallet_address}")
    def _get_or_create_wallet(self):
        if self.wallet_file and os.path.exists(self.wallet_file):
            try:
                w=json.load(open(self.wallet_file,'r'))
                print(f"{Fore.GREEN}Loaded existing wallet from {self.wallet_file}")
                pk=w['private_key']
                pk=f'0x{pk}'if not pk.startswith('0x')else pk
                kb=binascii.unhexlify(pk[2:])
                if len(kb)==32:return pk,w['address']
                else:return self._create_and_save_wallet()
            except Exception as e:
                print(f"{Fore.RED}Error loading wallet: {str(e)}")
                return self._create_and_save_wallet()
        else:return self._create_and_save_wallet()
    def _create_and_save_wallet(self):
        a=Account.create()
        pk=a.key.hex()
        pk=f'0x{pk}'if not pk.startswith('0x')else pk
        kb=binascii.unhexlify(pk[2:])
        ad=a.address.lower()
        wd={'private_key':pk,'address':ad,'created_at':time.strftime('%Y-%m-%d %H:%M:%S')}
        if self.wallet_file:
            pathlib.Path(os.path.dirname(self.wallet_file)or'.').mkdir(parents=True,exist_ok=True)
            json.dump(wd,open(self.wallet_file,'w'),indent=2)
            print(f"{Fore.GREEN}Created new wallet and saved to {self.wallet_file}")
            print(f"{Fore.YELLOW}IMPORTANT: Backup your wallet file for future access!")
        return pk,ad
    def login_with_wallet(self):
        print(f"{Fore.BLUE}Requesting authentication message...")
        p={"address":self.wallet_address,"chain":1,"network":"evm"}
        try:
            r=self.session.post(f"{self.auth_url}/auth/request-message",json=p,headers=Config.get_headers())
            if r.status_code!=200:
                print(f"{Fore.RED}Failed to request message: {r.status_code}\n{r.text}")
                return False
            response_data=json.loads(r.text)
            m=response_data.get("message")
            n=response_data.get("nonce")
            self.private_key=f'0x{self.private_key}'if not self.private_key.startswith('0x')else self.private_key
            kb=binascii.unhexlify(self.private_key[2:])
            if len(kb)!=32:
                print(f"{Fore.RED}Invalid private key length: {len(kb)} bytes. Must be exactly a 32 byte private key.")
                return False
            a=Account.from_key(self.private_key)
            if a.address.lower()!=self.wallet_address.lower():
                print(f"{Fore.RED}Error: Private key {self.private_key} does not match wallet address {self.wallet_address}\n{Fore.RED}Derived address: {a.address.lower()}")
                return False
            sig=self.web3.eth.account.sign_message(encode_defunct(text=m),private_key=self.private_key).signature.hex()
            time.sleep(2)
            vp={"message":m,"nonce":n,"signature":sig,"address":self.wallet_address}
            vr=self.session.post(f"{self.auth_url}/auth/verify",json=vp,headers=Config.get_headers(with_user_agent=True))
            if vr.status_code!=200:
                print(f"{Fore.RED}Failed to verify signature: {vr.status_code}\n{vr.text}")
                return False
            self.cookies=vr.cookies
            print(f"{Fore.GREEN}Login successful!")
            return True
        except Exception as e:
            print(f"{Fore.RED}Error in login process: {str(e)}")
            return False
    def start_mining(self):
        print(f"{Fore.BLUE}Starting mining...")
        try:
            sr=self.session.get(f"{self.token_url}/api/v1/mine/status",headers=Config.get_headers())
            if sr.status_code==200:
                sd=json.loads(sr.text)
                if sd and sd.get('success')and sd.get('user',{}).get('miningActive',False):
                    print(f"{Fore.YELLOW}Mining is already active for this wallet. Mining rate: {sd.get('user',{}).get('miningRate',0)}")
                    return True
        except Exception as e:
            print(f"{Fore.YELLOW}Failed to check mining status: {str(e)}. Continuing...")
        p={"referralCode":self.referral_code}
        try:
            r=self.session.post(f"{self.token_url}/api/v1/mine/start",json=p,headers=Config.get_headers())
            if r.status_code==200:
                rs=json.loads(r.text)
                print(f"{Fore.GREEN}Mining started successfully: {rs.get('message')}")
                print(f"{Fore.GREEN}Mining rate: {rs.get('user',{}).get('miningRate',0)}")
                return True
            elif r.status_code==400 and"already in progress"in json.loads(r.text).get('message','').lower():
                print(f"{Fore.YELLOW}Mining already in progress for this wallet.")
                return True
            else:
                print(f"{Fore.RED}Failed to start mining: {r.status_code}\n{r.text}")
                return False
        except Exception as e:
            print(f"{Fore.RED}Exception when starting mining: {str(e)}")
            return False
    def do_checkin(self):
        print(f"{Fore.BLUE}Performing check-in...")
        r=self.session.post(f"{self.token_url}/api/v1/mine/checkin",json={},headers=Config.get_headers())
        if r.status_code!=200:
            print(f"{Fore.RED}Failed to check-in: {r.status_code}\n{r.text}")
            return False
        rs=json.loads(r.text)
        print(f"{Fore.GREEN}Check-in result: {rs.get('message')}")
        print(f"{Fore.GREEN}Mined tokens: {rs.get('user',{}).get('minedTokens',0)}")
        print(f"{Fore.GREEN}Next check-in available: {rs.get('user',{}).get('nextCheckInActive','')}")
        return True
    def run_automation(self):
        if not self.login_with_wallet():return False
        time.sleep(2)
        if not self.start_mining():
            print(f"{Fore.YELLOW}Mining may already be in progress. Continuing...")
        print(f"{Fore.GREEN}Mining started successfully.")
        time.sleep(2)
        return self.do_checkin()
class MultiAccountManager:
    def __init__(self,wallets_file=None,referral_code=None,proxy=None):
        self.wallets_file=wallets_file if wallets_file else Config.WALLETS_FILE
        self.referral_code=referral_code if referral_code else Config.DEFAULT_REFERRAL_CODE
        self.proxy=proxy
        self.requested_count=0
        self.wallets=self._load_or_create_wallets_file()
    def _load_or_create_wallets_file(self):
        if os.path.exists(self.wallets_file):
            try:
                w=json.load(open(self.wallets_file,'r'))
                print(f"{Fore.GREEN}Loaded {Fore.YELLOW}{len(w)}{Fore.GREEN} existing wallets from {self.wallets_file}")
                return w
            except Exception as e:
                print(f"{Fore.RED}Error loading wallets file: {str(e)}")
                return[]
        else:
            print(f"{Fore.YELLOW}No wallets file found at {self.wallets_file}. Creating new file.")
            pathlib.Path(os.path.dirname(self.wallets_file)or'.').mkdir(parents=True,exist_ok=True)
            json.dump([],open(self.wallets_file,'w'),indent=2)
            return[]
    def _save_wallets(self):
        json.dump(self.wallets,open(self.wallets_file,'w'),indent=2)
        print(f"{Fore.GREEN}Saved {Fore.YELLOW}{len(self.wallets)}{Fore.GREEN} wallets to {self.wallets_file}")
    def generate_wallets(self,count=None):
        c=count if count is not None else Config.DEFAULT_WALLET_COUNT
        cc=len(self.wallets)
        print(f"{Fore.BLUE}Generating {Fore.YELLOW}{c}{Fore.BLUE} new wallets to add to existing {Fore.YELLOW}{cc}{Fore.BLUE} wallets...")
        nw=[]
        for i in range(c):
            wallet=PrdtAutomation(wallet_file=None,referral_code=self.referral_code)
            nw.append(wallet)
            self.wallets.append({'private_key':wallet.private_key,'address':wallet.wallet_address,'created_at':time.strftime('%Y-%m-%d %H:%M:%S'),'index':cc+i+1,'last_used':None})
            if(i+1)%10==0:self._save_wallets()
            print(f"{Fore.GREEN}Generated wallet #{cc+i+1}: {Fore.YELLOW}{wallet.wallet_address}")
            time.sleep(random.uniform(0.1,0.3))
        self._save_wallets()
        return self.wallets[-c:]
    def generate_and_process_wallets(self,count=None,delay_between_accounts=None):
        c=count if count is not None else Config.DEFAULT_WALLET_COUNT
        d=delay_between_accounts if delay_between_accounts is not None else Config.DEFAULT_DELAY_BETWEEN_ACCOUNTS
        self.requested_count=c
        cc=len(self.wallets)
        sw=0
        p=0
        print(f"{Fore.BLUE}Generating and processing {Fore.YELLOW}{c}{Fore.BLUE} new wallets...")
        for i in range(c):
            try:
                b=PrdtAutomation(wallet_file=None,referral_code=self.referral_code,proxy=self.proxy)
                wd={'private_key':b.private_key,'address':b.wallet_address,'created_at':time.strftime('%Y-%m-%d %H:%M:%S'),'index':len(self.wallets)+1,'last_used':None}
                print(f"\n{Fore.CYAN}[{i+1}/{c}] Generated new wallet #{len(self.wallets)+1}: {Fore.YELLOW}{b.wallet_address}")
                print(f"{Fore.BLUE}Processing new wallet: {Fore.YELLOW}{b.wallet_address}")
                time.sleep(1.5)
                success=b.run_automation()
                if success:
                    sw+=1
                    wd['last_used']=time.strftime('%Y-%m-%d %H:%M:%S')
                    self.wallets.append(wd)
                    self._save_wallets()
                else:
                    print(f"{Fore.YELLOW}Automation failed. Wallet not saved.")
                p+=1
                if i<c-1:
                    dl=random.uniform(d*0.8,d*1.2)
                    print(f"{Fore.BLUE}Waiting {Fore.YELLOW}{dl:.2f}{Fore.BLUE} seconds before next account...")
                    time.sleep(dl)
            except Exception as e:
                print(f"{Fore.RED}Error processing new wallet {b.wallet_address}: {str(e)}")
                print(f"{Fore.YELLOW}Automation failed. Wallet not saved.")
                time.sleep(2)
        print(f"\n{Fore.GREEN}=== Summary ===")
        print(f"{Fore.GREEN}Total new wallets processed: {Fore.YELLOW}{p}")
        print(f"{Fore.GREEN}Successfully completed and saved: {Fore.YELLOW}{sw}")
        if p>0:print(f"{Fore.GREEN}Success rate: {Fore.YELLOW}{(sw/p)*100:.1f}%")
        print(f"{Fore.GREEN}===============")
if __name__=="__main__":
    print(f"{Fore.CYAN}"+"="*70)
    print(f"{Fore.CYAN}                   PRDT Finance Automation Tool")
    print(f"{Fore.CYAN}                   ------------------------")
    print(f"{Fore.CYAN}"+"="*70)
    up=None
    cp=None
    while up is None:
        pc=input(f"{Fore.GREEN}Gunakan proxy? (y/n) [default: y]: {Fore.YELLOW}").strip().lower()
        if pc==""or pc=="y"or pc=="yes":
            up=True
            print(f"{Fore.GREEN}Menggunakan proxy.")
            if not Config.PROXY or Config.PROXY.strip()=="":
                print(f"{Fore.RED}ERROR: Proxy default kosong! Silakan set variabel PROXY di class Config.")
                sys.exit(1)
            print(f"{Fore.GREEN}Menggunakan proxy default: {Fore.CYAN}{Config.PROXY}")
            cp=Config.PROXY
        elif pc=="n"or pc=="no":
            up=False
            print(f"{Fore.YELLOW}Tidak menggunakan proxy.")
        else:
            print(f"{Fore.RED}Input tidak valid. Masukkan 'y' atau 'n'.")
    while True:
        try:
            wc=input(f"{Fore.GREEN}Berapa banyak wallet yang ingin dibuat? [default: {Config.DEFAULT_WALLET_COUNT}]: {Fore.YELLOW}")
            wc=Config.DEFAULT_WALLET_COUNT if wc.strip()==""else int(wc)
            if wc==Config.DEFAULT_WALLET_COUNT:
                print(f"{Fore.GREEN}Menggunakan jumlah default: {Fore.YELLOW}{wc}{Fore.GREEN} wallet")
            if wc<=0:
                print(f"{Fore.YELLOW}Jumlah wallet harus lebih dari 0. Silakan coba lagi.")
                continue
            if wc!=Config.DEFAULT_WALLET_COUNT:
                print(f"{Fore.GREEN}Akan membuat {Fore.YELLOW}{wc}{Fore.GREEN} wallet")
            break
        except ValueError:
            print(f"{Fore.RED}Input tidak valid. Masukkan angka, contoh: 50")
            continue
    MultiAccountManager(wallets_file=Config.WALLETS_FILE,referral_code=Config.DEFAULT_REFERRAL_CODE,proxy=cp if up else None).generate_and_process_wallets(count=wc,delay_between_accounts=Config.DEFAULT_DELAY_BETWEEN_ACCOUNTS)