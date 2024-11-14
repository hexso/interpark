from PyQt5.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox
from PyQt5.QtWidgets import QPushButton, QListWidget, QListWidgetItem, QGroupBox, QComboBox, QMessageBox, QTimeEdit, QCheckBox
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIntValidator, QIcon
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
import chromedriver_autoinstaller
from webdriver_manager.chrome import ChromeDriverManager  # 설치 필요
import time
import datetime
import re
import sys
import requests
import threading
import random

TIMESLEEP = 0.05

driver = None

headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'referer': 'https://tickets.melon.com/',
}

class Worker(QThread): # 브라우저 돌아가는 스레드
    printLog = pyqtSignal(str)
    taskDone = pyqtSignal()
    def __init__(self, parent, id, pw, ticket_id, scheduleNo='10001'):
        super().__init__(parent)
        self.running = True
        self.parent = parent
        self.finished = False
        self.id = id
        self.pw = pw
        self.ticket_id = ticket_id
        self.scheduleNo = scheduleNo
        self.driver = None
        self.member_key = None
        self.driver = None
        self.tempkey = None
        self.nflActId = None
        self.real_key = None

    # 1. 아마 아이디마다 고유의 멤버키가 있을것으로 예상된다. 이것을 먼저 받아야 한다.
    def get_memberkey(self):
        url = "https://tktapi.melon.com/api/prersrv/usercond.json"
        params = {
            "prodId": self.ticket_id,
            "pocCode": "SC0002",
            "sellTypeCode": "ST0002",
            "sellCondNo": "1",
            "autheTypeCode": "BG0010",
            "btnType": "B",
            "v": "1",
            "requestservicetype": "P"
        }

        # `requests.Session()` 초기화
        session = requests.Session()

        # Selenium에서 쿠키 가져오기
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        # User-Agent와 같은 헤더 설정
        headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")  # 현재 브라우저의 User-Agent 가져오기
        }

        response = session.get(url, headers=headers, params=params)
        member_key = response.json()['data']['memberKey']
        self.member_key = member_key
        return member_key

    #2. 일시적으로 생성되는 key 두개를 받는다. nflActId,key
    def get_temp_keys(self):
        headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")  # 현재 브라우저의 User-Agent 가져오기
        }
        url = f"https://tktapi.melon.com/api/product/prodKey.json"
        params = {
            "prodId": self.ticket_id,
            "scheduleNo": self.scheduleNo,
            "v": "1",
            "requestservicetype": "P"
        }

        # `requests.Session()` 초기화
        session = requests.Session()
        # Selenium에서 쿠키 가져오기
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        response = session.get(url, headers=headers, params=params)
        return response

    # 3. nflActId,key들을 통해 실제 접속을 위한 key를 받는다
    def get_real_key(self):
        headers = {
            "User-Agent": self.driver.execute_script("return navigator.userAgent;")  # 현재 브라우저의 User-Agent 가져오기
        }
        url = f"https://tktapi.melon.com/api/product/prodKey.json"
        params = {
            "prodId": self.ticket_id,
            "scheduleNo": self.scheduleNo,
            "v": "1",
            "requestservicetype": "P"
        }

        # `requests.Session()` 초기화
        session = requests.Session()
        # Selenium에서 쿠키 가져오기
        for cookie in self.driver.get_cookies():
            session.cookies.set(cookie['name'], cookie['value'])

        response = session.get(url, headers=headers, params=params)
        self.tempkey = response['key']
        sentence = response['nflActId']
        match = re.search(r"key=([^&]*)", sentence)
        if match:
            key_value = match.group(1) + '&'
            print(key_value)
        self.real_key = key_value

    #4. 새로운 페이지 들어가기
    def enter_ticket_page(self):
        # 예약 정보 작성
        self.driver.execute_script("window.open('');")
        tabs = self.driver.window_handles
        self.driver.switch_to.window(tabs[1])

        data = {
            'prodId': self.ticket_id,
            'pocCode': 'SC0002',
            'scheduleNo': '100001',
            'sellCondNo': '1',
            'sellTypeCode': 'ST0002',
            't': '',
            'tYn': 'Y',
            'chk': self.tempkey,
            'netfunnel_key': self.nflActId,
            'autheTypeCode': 'BG0010'
        }

        # JavaScript를 사용해 폼 데이터 제출하기
        script = f"""
            var form = document.createElement('form');
            form.method = 'POST';
            form.action = 'https://ticket.melon.com/reservation/popup/onestop.htm';
            form.style.display = 'none';

            var params = {data};
            for (var key in params) {{
                if (params.hasOwnProperty(key)) {{
                    var input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    input.value = params[key];
                    form.appendChild(input);
                }}
            }}

            document.body.appendChild(form);
            form.submit();
        """

        # Selenium을 사용하여 JavaScript 실행
        self.driver.execute_script(script)

    def run(self):
        global driver
        if driver == None:
            self.printLog.emit("조회를 먼저 눌러주세요")
            return

        self.driver = driver
        #멤버키를 먼저 받는다.
        self.get_memberkey()

        # 부모의 예약 시작 시간 불러오기
        target_time = self.parent.timeEdit.time().toPyTime()

        # 현재 시간 불러오기
        now = datetime.datetime.now()

        self.printLog.emit("예약 시작 시간까지 대기합니다..")

        # 예약 시작 시간 8초 전까지 대기
        while now < datetime.datetime(now.year, now.month, now.day, target_time.hour, target_time.minute,
                                      target_time.second) - datetime.timedelta(seconds=2):
            time.sleep(0.05)
            now = datetime.datetime.now()  # 현재 시간을 다시 업데이트

        self.printLog.emit("자 들어갑니다")

        self.threads = []
        thread_count = self.parent.sb_thread_count.value()
        def wait_list():
            while True:
                if not self.parent.running:
                    return
                if self.tempkey != None:
                    return
                thread_response = self.get_temp_keys()
                if 'key' in thread_response:
                    if thread_response['key'] != '':
                        self.tempkey = thread_response['key']
                        self.nflActId = thread_response['nflActId']
                        return
                time.sleep(TIMESLEEP)

        for i in range(thread_count):
            thread = threading.Thread(target=wait_list)
            thread.start()
            self.printLog.emit(f'{i+1}번째 스레드가 실행되었습니다.')
            self.threads.append(thread)

        self.get_real_key()
        self.enter_ticket_page()
        self.printLog.emit('예매 대기열을 불러왔습니다.')





class ImportGoodsDetail(QThread):
    loadFinished = pyqtSignal(dict)
    printLog = pyqtSignal(str)

    def __init__(self, parent, ticket_id):
        super().__init__(parent)
        self.parent = parent
        self.ticket_id = ticket_id

    def run(self):
        global driver
        #get title name
        url = f"https://ticket.melon.com/performance/index.htm?prodId={self.ticket_id}"
        response = requests.get(url, headers=headers)
        # BeautifulSoup 객체 생성
        soup = BeautifulSoup(response.text, 'html.parser')

        # <meta> 태그 중 property="og:title" 인 요소 찾기
        meta_tag = soup.find('meta', property='og:title')

        if meta_tag:
            title = meta_tag.get('content')
            print(title)
        else:
            title = "해당 타이틀을 찾을 수 없음. 그러나 정상작동할껄?"
            print("해당 메타 태그를 찾을 수 없습니다.")

        ticket_info_url = "https://tktapi.melon.com/api/product/schedule/daylist.json"
        params = {
            "prodId": self.ticket_id,
            "pocCode": "SC0002",
            "perfTypeCode": "GN0001",
            "sellTypeCode": "ST0002", #선예매는 ST0002, 일반예매는 ST0001 #Todo: 일반예매도 가능하게끔 개선 필요
            "corpCodeNo": "",
            "prodTypeCode": "PT0001", #일반 상품 PT0001 -> 이건 따로 수정할 필요 없어 보임
            "reflashYn": "N",  #일반 상품은 reflashYn=N이로 설정된다.
            "requestservicetype": "P"
        }
        
        response = requests.get(ticket_info_url, headers=headers, params=params)
        response = response.json()['data']
        print(response)

        genreName = ""
        goodsName = title

        sequences = []

        for data in response['perfDaylist']:
            sequences.append({
                'playSeq': data['groupSch'],
                'playDate': data['perfDay'],
                'playTime': '',
            })

        self.printLog.emit(f'공연 정보를 불러왔습니다.')

        self.loadFinished.emit({
            'genreName': genreName,
            'goodsName': goodsName,
            'playEndDate': '',
            'playStartDate': '',
            'sequences': sequences
        })

        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        chromedriver_autoinstaller.install()
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(f"https://ticket.melon.com/performance/index.htm?prodId={self.ticket_id}")
        self.printLog.emit('멜론티켓 로그인을 해주세요.')

class Form(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

        self.running = False
        self.tickets_detail = None

        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_clear_log.clicked.connect(self.lw_log.clear)
        self.btn_find.clicked.connect(self.fetch_goods_detail)

    def init_ui(self):
        self.vbox = QVBoxLayout()
        self.setLayout(self.vbox)

        self.setWindowIcon(QIcon('icon.png'))
        self.setWindowTitle('멜론 대기열 접속기')

        self.hbox_settings = QHBoxLayout()

        self.lb_id = QLabel('아이디')
        self.le_id = QLineEdit()

        self.lb_pw = QLabel('비밀번호')
        self.le_pw = QLineEdit()
        self.le_pw.setEchoMode(QLineEdit.Password)

        self.lb_ticket_id = QLabel('공연 ID')
        self.le_ticket_id = QLineEdit()
        # 숫자만 입력가능하게
        self.le_ticket_id.setValidator(QIntValidator())

        self.btn_find = QPushButton('공연 찾기')

        # 숫자만 입력가능하게
        self.le_ticket_id.setValidator(QIntValidator())

        self.hbox_settings.addWidget(self.lb_id)
        self.hbox_settings.addWidget(self.le_id)
        self.hbox_settings.addWidget(self.lb_pw)
        self.hbox_settings.addWidget(self.le_pw)
        self.hbox_settings.addWidget(self.lb_ticket_id)
        self.hbox_settings.addWidget(self.le_ticket_id)
        self.hbox_settings.addWidget(self.btn_find)

        self.gb_settings = QGroupBox('설정')
        self.gb_settings.setLayout(self.hbox_settings)

        self.vbox.addWidget(self.gb_settings)

        self.vbox_log = QVBoxLayout()
        self.lw_log = QListWidget()
        self.vbox_log.addWidget(self.lw_log)

        self.gb_ticket_detail = QGroupBox('공연 정보')
        self.hbox_ticket_detail = QHBoxLayout()

        self.lb_ticket_genre = QLabel('장르: ')
        self.lb_ticket_genre_value = QLabel('')

        self.lb_ticket_name = QLabel('공연명: ')
        self.lb_ticket_name_value = QLabel('')

        self.lb_ticket_start_date = QLabel('시작일: ')
        self.lb_ticket_start_date_value = QLabel('')

        self.lb_ticket_end_date = QLabel('종료일: ')
        self.lb_ticket_end_date_value = QLabel('')

        self.lb_ticket_seq = QLabel('회차: ')
        self.cmb_ticket_seq = QComboBox()
        # 콤보박스 내용물 크기에 맞게 조절
        self.cmb_ticket_seq.setSizeAdjustPolicy(QComboBox.AdjustToContents)

        self.lb_time = QLabel('예매 시작 시간: ')

        self.timeEdit = QTimeEdit()
        self.timeEdit.setDisplayFormat("HH:mm:ss")
        self.timeEdit.setTime(datetime.datetime.now().time())

        self.hbox_ticket_detail.addWidget(self.lb_ticket_genre)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_genre_value)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_name)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_name_value)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_start_date)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_start_date_value)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_end_date)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_end_date_value)
        self.hbox_ticket_detail.addWidget(self.lb_ticket_seq)
        self.hbox_ticket_detail.addWidget(self.cmb_ticket_seq)
        self.hbox_ticket_detail.addWidget(self.lb_time)
        self.hbox_ticket_detail.addWidget(self.timeEdit)

        self.gb_ticket_detail.setLayout(self.hbox_ticket_detail)

        self.vbox.addWidget(self.gb_ticket_detail)

        self.gb_log = QGroupBox('로그')
        self.gb_log.setLayout(self.vbox_log)

        self.vbox.addWidget(self.gb_log)

        self.hbox_control = QHBoxLayout()

        self.btn_start = QPushButton('시작')
        self.btn_stop = QPushButton('중지')
        self.btn_stop.setEnabled(False)
        self.cb_pre_sales = QCheckBox('선예매')
        self.lb_thread = QLabel("스레드 개수")
        self.sb_thread_count = QSpinBox()
        self.sb_thread_count.setMinimum(2)
        self.sb_thread_count.setMaximum(20)
        self.sb_thread_count.setValue(5)
        self.lb_pre_req = QLabel("스레드 선시작 (초)")
        self.sb_pre_req = QSpinBox()
        self.sb_pre_req.setMinimum(1)
        self.sb_pre_req.setMaximum(10)
        self.sb_pre_req.setValue(3)
        self.btn_clear_log = QPushButton('로그 지우기')

        self.hbox_control.addWidget(self.btn_start)
        self.hbox_control.addWidget(self.btn_stop)
        self.hbox_control.addWidget(self.cb_pre_sales)
        self.hbox_control.addWidget(self.lb_thread)
        self.hbox_control.addWidget(self.sb_thread_count)
        self.hbox_control.addWidget(self.lb_pre_req)
        self.hbox_control.addWidget(self.sb_pre_req)
        self.hbox_control.addWidget(self.btn_clear_log)

        self.gb_control = QGroupBox('제어')
        self.gb_control.setLayout(self.hbox_control)

        self.vbox.addWidget(self.gb_control)

    def fetch_goods_detail(self):
        ticket_id = self.le_ticket_id.text().replace(' ', '')
        if ticket_id == '':
            QMessageBox.warning(self, '경고', '공연 ID를 입력해주세요.')
            return

        try:
            int(ticket_id)
        except:
            QMessageBox.warning(self, '경고', '공연 ID는 숫자로 입력해주세요.')
            return

        self.btn_find.setEnabled(False)
        self.importGoodsDetail = ImportGoodsDetail(self, ticket_id)
        self.importGoodsDetail.loadFinished.connect(self.loadFinished)
        self.importGoodsDetail.start()

    @pyqtSlot(dict)
    def loadFinished(self, data):
        self.btn_find.setEnabled(True)
        self.lb_ticket_genre_value.setText(data['genreName'])
        self.lb_ticket_genre_value.setStyleSheet('font-weight: bold; color: green;')
        self.lb_ticket_name_value.setText(data['goodsName'])
        self.lb_ticket_name_value.setStyleSheet('font-weight: bold; color: blue;')
        self.lb_ticket_start_date_value.setText(data['playStartDate'])
        self.lb_ticket_start_date_value.setStyleSheet('font-weight: bold; color: red;')
        self.lb_ticket_end_date_value.setText(data['playEndDate'])
        self.lb_ticket_end_date_value.setStyleSheet('font-weight: bold; color: red;')

        self.cmb_ticket_seq.clear()
        for seq in data['sequences']:
            self.cmb_ticket_seq.addItem(
                f"{seq['playSeq']}: {seq['playDate'][:4]}년 {seq['playDate'][4:6]}월 {seq['playDate'][6:8]}일 {seq['playTime'][:2]}시 {seq['playTime'][2:]}분")

        self.tickets_detail = data

    def start(self):
        inter_id = self.le_id.text().replace(' ', '')
        inter_pw = self.le_pw.text().replace(' ', '')
        inter_ticket_id = self.le_ticket_id.text().replace(' ', '')

        if inter_id == '':
            QMessageBox.warning(self, '경고', '아이디를 입력해주세요.')
            return

        if inter_pw == '':
            QMessageBox.warning(self, '경고', '비밀번호를 입력해주세요.')
            return

        if inter_ticket_id == '':
            QMessageBox.warning(self, '경고', '공연 ID를 입력해주세요.')
            return

        try:
            int(inter_ticket_id)
        except:
            QMessageBox.warning(self, '경고', '공연 ID는 숫자로 입력해주세요.')
            return

        if self.tickets_detail is None:
            QMessageBox.warning(self, '경고', '공연 정보를 불러와주세요.')
            return

        playSeq = "100001" # Todo: 공연이 열리기전에는 알수 없으므로 제일 첫번째 공연을 예매한다

        self.worker = Worker(self, inter_id, inter_pw, inter_ticket_id, playSeq)
        self.worker.printLog.connect(self.printLog)
        self.worker.taskDone.connect(self.taskDone)
        self.worker.start()

        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    @pyqtSlot(str)
    def printLog(self, text):
        currenttime_str = datetime.datetime.now().strftime('%H:%M:%S')
        item = QListWidgetItem(f'[{currenttime_str}] {text}')
        self.lw_log.addItem(item)

        if self.lw_log.count() > 400:
            self.lw_log.takeItem(0)

        self.lw_log.scrollToBottom()

    @pyqtSlot()
    def taskDone(self):
        self.worker.driver.quit()
        self.worker.quit()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.printLog('프로그램이 종료되었습니다.')

    def stop(self):
        self.btn_stop.setEnabled(False)
        self.printLog('브라우저를 중지 중입니다...')
        self.worker.running = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = Form()
    form.show()
    sys.exit(app.exec_())
    # chromedriver_autoinstaller.install()
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
    # time.sleep(1)
    # url = f"https://ticket.melon.com/performance/index.htm?prodId=210619"
    # driver.get(url)
    # time.sleep(10)