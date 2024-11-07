
from PyQt5.QtWidgets import QApplication, QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QSpinBox
from PyQt5.QtWidgets import QPushButton, QListWidget, QListWidgetItem, QGroupBox, QComboBox, QMessageBox, QTimeEdit, QCheckBox
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIntValidator, QIcon
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
import chromedriver_autoinstaller
from webdriver_manager.chrome import ChromeDriverManager  # 설치 필요
import time
import datetime
import sys
import requests
import threading
import random

first_response = None # 첫번째 응답


def request_waitlist(url, session, parent): # 대기열 요청 함수
    global first_response
    while True:
        if not parent.running:
            return
        try:
            delay_random = random.randint(1, 9) / 100
            time.sleep(delay_random)
            response = session.get(url)
            resp = response.json()
            print(resp)
            waiting_url = resp['data']
            if waiting_url == 'NP':
                waiting_url = None
        except Exception as e:
            print(e)
            continue
        else:
            if waiting_url != None :
                first_response = waiting_url
                break
            else:
                continue
    return


class Worker(QThread): # 브라우저 돌아가는 스레드
    printLog = pyqtSignal(str)
    taskDone = pyqtSignal()
    def __init__(self, parent, id, pw, ticket_id, channelCode='sp', preSales='N', playDate='20241012', playSeq='001'):
        super().__init__(parent)
        self.running = True
        self.parent = parent
        self.finished = False
        self.id = id
        self.pw = pw
        self.ticket_id = ticket_id
        self.channelCode = channelCode
        self.preSales = preSales
        self.playDate = playDate
        self.playSeq = playSeq

    def run(self):
        global first_response

        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        chromedriver_autoinstaller.install()
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

        self.printLog.emit('인터파크 로그인을 시작합니다.')

        self.driver.get("https://accounts.interpark.com/login/form")
        self.driver.find_element(By.ID, "userId").send_keys(self.id)
        time.sleep(1)
        self.driver.find_element(By.ID, "userPwd").send_keys(self.pw)
        time.sleep(1)
        self.driver.find_element(By.ID, "btn_login").click()
        time.sleep(10)
        self.driver.get(f"https://tickets.interpark.com/goods/{self.ticket_id}")

        session = requests.Session()
        for cookie in self.driver.get_cookies():
            c = {cookie['name']: cookie['value']}
            session.cookies.update(c)

        # 새 탭 열기
        self.driver.execute_script("window.open('');")
        # 탭 리스트 가져오기
        tabs = self.driver.window_handles
        # 탭 이동

        self.driver.switch_to.window(tabs[1])


        url = f"https://api-ticketfront.interpark.com/v1/goods/{self.ticket_id}/waiting?channelCode={self.channelCode}&preSales={self.preSales}&playDate={self.playDate}&playSeq={self.playSeq}"


        # 부모의 예약 시작 시간 불러오기
        target_time = self.parent.timeEdit.time().toPyTime()

        # 현재 시간 불러오기
        now = datetime.datetime.now()

        self.printLog.emit("예약 시작 시간까지 대기합니다..")

        pre_req_time = self.parent.sb_pre_req.value()

        # 예약 시작 시간 8초 전까지 대기
        while now < datetime.datetime(now.year, now.month, now.day, target_time.hour, target_time.minute, target_time.second) - datetime.timedelta(seconds=pre_req_time + 5):
            time.sleep(0.05)
            now = datetime.datetime.now()  # 현재 시간을 다시 업데이트

        for i in range(1, 6):
            self.printLog.emit(f'예매 시작시간까지 {5+pre_req_time-i}초, 대기열 요청 전송 시작까지 {6-i}초 남음...')
            time.sleep(1)

        self.threads = []
        thread_count = self.parent.sb_thread_count.value()

        for i in range(thread_count):
            thread = threading.Thread(target=request_waitlist, args=(url, session, self))
            thread.start()
            self.printLog.emit(f'{i+1}번째 스레드가 실행되었습니다.')
            self.threads.append(thread)

        while first_response is None:
            if not self.running:
                self.printLog.emit('대기 중 사용자가 프로그램을 종료했습니다.')
                self.taskDone.emit()
                return
            time.sleep(0.1)
        
        self.printLog.emit('예매 대기열을 불러왔습니다.')
        
        self.driver.get(first_response)

        while True:
            if not self.running:
                break
        self.taskDone.emit()

class ImportGoodsDetail(QThread):
    loadFinished = pyqtSignal(dict)
    printLog = pyqtSignal(str)

    def __init__(self, parent, ticket_id):
        super().__init__(parent)
        self.parent = parent
        self.ticket_id = ticket_id

    def run(self):
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'referer': 'https://tickets.interpark.com/',
        }
        summary_url = f"https://api-ticketfront.interpark.com/v1/goods/{self.ticket_id}/summary?goodsCode={self.ticket_id}&priceGrade=&seatGrade="
        response = requests.get(summary_url, headers=headers)
        response = response.json()['data']
        print(response)

        genreName = response['genreName']
        goodsName = response['goodsName']
        playEndDate = response['playEndDate']
        playStartDate = response['playStartDate']

        seq_url = f"https://api-ticketfront.interpark.com/v1/goods/24011622/playSeq?endDate={playEndDate}&goodsCode={self.ticket_id}&isBookableDate=true&page=1&pageSize=1550&startDate={playStartDate}"
        response = requests.get(seq_url, headers=headers)
        response = response.json()['data']
        print(response)

        sequences = []

        for data in response:
            sequences.append({
                'playSeq': data['playSeq'],
                'playDate': data['playDate'],
                'playTime': data['playTime'],
            })
        
        self.printLog.emit(f'공연 정보를 불러왔습니다.')

        self.loadFinished.emit({
            'genreName': genreName,
            'goodsName': goodsName,
            'playEndDate': playEndDate,
            'playStartDate': playStartDate,
            'sequences': sequences
        })

        
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
        self.setWindowTitle('인터파크 대기열 접속기')

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

        #숫자만 입력가능하게
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

        self.lb_ticket_genre= QLabel('장르: ')
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
            self.cmb_ticket_seq.addItem(f"{seq['playSeq']}: {seq['playDate'][:4]}년 {seq['playDate'][4:6]}월 {seq['playDate'][6:8]}일 {seq['playTime'][:2]}시 {seq['playTime'][2:]}분")

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
        
        channelCode = 'pc'
        if self.tickets_detail['genreName'] == '콘서트':
            channelCode = 'pc'
        elif self.tickets_detail['genreName'] == '스포츠':
            channelCode = 'sp'

        preSales = 'N'
        if self.cb_pre_sales.isChecked():
            preSales = 'Y'

        playDate = self.tickets_detail['sequences'][self.cmb_ticket_seq.currentIndex()]['playDate']

        playSeq = self.tickets_detail['sequences'][self.cmb_ticket_seq.currentIndex()]['playSeq']
            
        self.worker = Worker(self, inter_id, inter_pw, inter_ticket_id, channelCode, preSales, playDate, playSeq)
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

if __name__ == '__main__':
    app = QApplication(sys.argv)
    form = Form()
    form.show()
    sys.exit(app.exec_())