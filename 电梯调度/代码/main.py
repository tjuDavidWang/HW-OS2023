import sys
import os
from enum import Enum
from functools import partial
import ui_mainwindow
from PyQt5.QtCore import QThread, QMutex, QTimer
from PyQt5 import QtWidgets, QtGui, QtCore

# 常量
ELEVATOR_NUM = 5  # 电梯数量
FLOOR_NUM = 20  # 电梯层数
MOVE_TIME = 1000  # 上升下降时间
DOOR_OPEN_AND_CLOSE_TIME = 2000  # 电梯开关门时间
BUTTON_COLOR = (255, 255, 255)  # 按钮未被按下的颜色
BUTTON_CLICKED_COLOR = (255, 255, 0)  # 按钮按下的颜色(黄色)
ELEVATOR_COLOR = (127, 255, 170)  # 电梯运行中的颜色(绿色)
DOOR_OPERATION_COLOR = (255, 255, 0)  # 电梯开关门时的中间色
WARNING_BUTTON_COLOR = (250, 128, 114)  # 报警按钮颜色(粉红色)


# 电梯的状态
class ELEVATOR_STATE(Enum):
    DOWN = -1
    NORMAL = 0
    UP = 1
    FAULT = 2
    DOOR = 3

# 电梯的移动状态
class MOVE_STATE(Enum):
    UP = 1
    DOWN = -1

# 外部按钮产生的任务的分配状态
class TASK_STATE(Enum):
    UNASSIGNED = 0
    WAITING = 1
    FINISHED = 2


# mutex全局互斥锁
mutex = QMutex()


class OuterTask:
    '''
    外部请求的封装
    :target_floor:目标楼层
    :move_state:运动状态
    :task_state：任务状态
    '''

    def __init__(self, target_floor, move_state, state=TASK_STATE.UNASSIGNED):
        self.floor = target_floor  # 目标楼层
        self.move_state = move_state  # 需要的电梯运行方向
        self.task_state = state  # 是否完成（默认未完成）


class MainWindow(QtWidgets.QMainWindow):
    """
    整个UI界面，详细定义见ui_mainwindow.py
    """

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = ui_mainwindow.Ui_MainWindow()
        self.ui.setupUi(self)

        # 初始化一系列按钮
        self.list_widgets = []
        self.elevator_lcds = []
        self.elevator_arrows = []
        self.elevator_buttons = []
        self.external_up_buttons = []
        self.external_down_buttons = []
        self.elevator_warning_buttons = []

        # 定时器 用于定时更新UI界面
        self.timer = QTimer()

        # 初始化 UI 元素
        self.init_ui_elements()

    def init_ui_elements(self):
        '''
        初始化ui界面
        :return:
        '''
        self.setWindowTitle("电梯调度")
        self.list_widgets = [self.ui.listWidget_1, self.ui.listWidget_2, self.ui.listWidget_3, self.ui.listWidget_4,
                             self.ui.listWidget_5]
        self.elevator_lcds = [self.ui.digit_1, self.ui.digit_2, self.ui.digit_3, self.ui.digit_4, self.ui.digit_5]
        self.elevator_arrows = [self.ui.arrow_1, self.ui.arrow_2, self.ui.arrow_3, self.ui.arrow_4, self.ui.arrow_5]
        self.up_arrow = QtGui.QPixmap(QtGui.QImage("img/arrow_up.png").scaled(32, 32))
        self.down_arrow = QtGui.QPixmap(QtGui.QImage("img/arrow_down.png").scaled(32, 32))
        self.elevator_warning_buttons = [self.ui.Warning_1, self.ui.Warning_2, self.ui.Warning_3, self.ui.Warning_4,
                                         self.ui.Warning_5]

        for elevator_id in range(ELEVATOR_NUM):
            elevator_buttons_i = []
            for floor_id in range(FLOOR_NUM):
                btn = getattr(self.ui, f"elevator_button_{floor_id + 1}_{elevator_id + 1}")
                elevator_buttons_i.append(btn)
                btn.setText(f"{floor_id + 1}")
                btn.clicked.connect(partial(self.elevator_button_clicked, elevator_id, floor_id))

                if elevator_id < 2:
                    external_btn = getattr(self.ui, f"elevator_button_{floor_id + 1}_{elevator_id + 6}")
                    if elevator_id == 0:
                        self.external_up_buttons.append(external_btn)
                        if floor_id != FLOOR_NUM - 1:
                            external_btn.setText("▲")
                            external_btn.clicked.connect(
                                partial(self.external_direction_button_clicked, floor_id, MOVE_STATE.UP))
                        else:
                            external_btn.setText("")

                    else:
                        self.external_down_buttons.append(external_btn)
                        if floor_id != 0:
                            external_btn.setText("▼")
                            external_btn.clicked.connect(
                                partial(self.external_direction_button_clicked, floor_id, MOVE_STATE.DOWN))
                        else:
                            external_btn.setText("")

            self.elevator_buttons.append(elevator_buttons_i)

        for elevator_id in range(5):
            self.elevator_warning_buttons[elevator_id].clicked.connect(
                partial(self.elevator_warning_button_clicked, elevator_id))

        for arrow in self.elevator_arrows:
            arrow.setPixmap(QtGui.QPixmap())

        # 设置定时，定时
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update)
        self.timer.start()

        self.show()

    def elevator_button_clicked(self, elevator_id, floor_id):
        '''
        当电梯内部按钮被点击时
        :param elevator_id: 电梯的index
        :param floor_id: 楼层的index
        :return:
        '''
        # 互斥锁：一次只能点一个电梯按钮
        mutex.lock()

        # 电梯故障，不处理按键
        if elevator_states[elevator_id] == ELEVATOR_STATE.FAULT:
            mutex.unlock()
            return

        # 楼层与电梯处在的楼层相同则不处理
        if floor_id == elevator_cur_floor[elevator_id]:
            mutex.unlock()
            return

        # 将按键加入任务列表中
        if floor_id > elevator_cur_floor[elevator_id] and floor_id not in elevator_up_target_list[elevator_id]:
            elevator_up_target_list[elevator_id].append(floor_id)
            elevator_up_target_list[elevator_id].sort()
        elif floor_id < elevator_cur_floor[elevator_id] and floor_id not in elevator_down_target_list[elevator_id]:
            elevator_down_target_list[elevator_id].append(floor_id)
            elevator_down_target_list[elevator_id].sort(reverse=True)
        self.elevator_buttons[elevator_id][floor_id].setStyleSheet("background-color : rgb" + str(BUTTON_CLICKED_COLOR))

        mutex.unlock()

        # self.show_current_position(floor_id, elevator_id)

    def elevator_warning_button_clicked(self, elevator_id):
        '''
        电梯的报警键被点击
        :param elevator_id: 电梯的index
        :return:
        '''
        mutex.lock()
        # 一开始处于正常状态
        if elevator_states[elevator_id] != ELEVATOR_STATE.FAULT:
            elevator_states[elevator_id] = ELEVATOR_STATE.FAULT
            # 回到一楼
            elevator_cur_floor[elevator_id] = 0
            # 可以开放锁，供其他使用
            mutex.unlock()

            self.elevator_warning_buttons[elevator_id].setStyleSheet(
                "background-color : rgb" + str(WARNING_BUTTON_COLOR))
            self.elevator_warning_buttons[elevator_id].setText("正常")
            for btn in self.elevator_buttons[elevator_id]:
                btn.setStyleSheet("background-color : rgb" + str(BUTTON_COLOR))
            # 涂成粉红色
            for i in range(FLOOR_NUM):
                self.paint_item(elevator_id, i, WARNING_BUTTON_COLOR)
        # 一开始处于报警状态：恢复正常
        else:
            elevator_states[elevator_id] = ELEVATOR_STATE.NORMAL
            # 可以开放锁，供其他使用
            mutex.unlock()

            self.elevator_warning_buttons[elevator_id].setStyleSheet("background-color : None")
            self.elevator_warning_buttons[elevator_id].setText("报警")

            for i in range(FLOOR_NUM):
                self.paint_item(elevator_id, i)

    def external_direction_button_clicked(self, floor_id, move_state):
        '''
        外界请求处理
        :param floor_id: 楼层
        :param move_state:需求方向
        :return:
        '''
        # 互斥锁
        mutex.lock()

        # 检测是否所有电梯均已经发生故障
        no_elevator_left = True
        for i in range(ELEVATOR_NUM):
            if elevator_states[i] != ELEVATOR_STATE.FAULT:
                no_elevator_left = False
        if no_elevator_left == True:
            print("所有电梯均已经发生故障")
            mutex.unlock()
            return

        task = OuterTask(floor_id, move_state)

        # 考虑重复点击的情况
        if task not in outer_tasks_list:
            outer_tasks_list.append(task)

            move_states = None
            if move_state == MOVE_STATE.UP:
                self.external_up_buttons[floor_id].setStyleSheet("background-color : rgb" + str(BUTTON_CLICKED_COLOR))
            elif move_states == MOVE_STATE.DOWN:
                self.external_down_buttons[floor_id].setStyleSheet("background-color : rgb" + str(BUTTON_CLICKED_COLOR))

        mutex.unlock()

    def paint_item(self, elevator_id, floor_id, color=(255, 255, 255), word=""):
        """
        展示电梯的运行状态
        :param elevator_id: 电梯index
        :param floor_id: 楼层index
        :param color: 颜色rgb三元组
        :param word: 输入文字
        :return:
        """
        brush = QtGui.QBrush(QtGui.QColor(*color))
        brush.setStyle(QtCore.Qt.SolidPattern)
        self.list_widgets[elevator_id].item(19 - floor_id).setBackground(brush)
        self.list_widgets[elevator_id].item(19 - floor_id).setText(word)

    def update(self):
        """
        用于刷新界面
        :return:
        """
        mutex.lock()
        for elevator_id in range(ELEVATOR_NUM):
            # 实时更新楼层
            if elevator_states[elevator_id] == ELEVATOR_STATE.UP:
                self.elevator_arrows[elevator_id].setPixmap(self.up_arrow)
            elif elevator_states[elevator_id] == ELEVATOR_STATE.DOWN:
                self.elevator_arrows[elevator_id].setPixmap(self.down_arrow)
            else:
                self.elevator_arrows[elevator_id].setPixmap(QtGui.QPixmap())
            self.elevator_lcds[elevator_id].display(str(elevator_cur_floor[elevator_id] + 1))

            # 对内部的按钮，如果在开门或关门状态的话，则设进度条
            if elevator_states[elevator_id] == ELEVATOR_STATE.DOOR:
                self.elevator_buttons[elevator_id][elevator_cur_floor[elevator_id]].setStyleSheet(
                    "background-color : rgb(255,255" + str(int(255 * (1 - elevator_door_process_bar[elevator_id]))))
                red = ELEVATOR_COLOR[0] + int((-2 * abs(elevator_door_process_bar[elevator_id] - 0.5) + 1) * (
                        DOOR_OPERATION_COLOR[0] - ELEVATOR_COLOR[0]))
                green = ELEVATOR_COLOR[1] + int((-2 * abs(elevator_door_process_bar[elevator_id] - 0.5) + 1) * (
                        DOOR_OPERATION_COLOR[1] - ELEVATOR_COLOR[1]))
                blue = ELEVATOR_COLOR[2] + int((-2 * abs(elevator_door_process_bar[elevator_id] - 0.5) + 1) * (
                        DOOR_OPERATION_COLOR[2] - ELEVATOR_COLOR[2]))
                color = (red, green, blue)
                if elevator_door_process_bar[elevator_id] < 1 / 4:
                    self.paint_item(elevator_id, elevator_cur_floor[elevator_id], color, "           开门中")
                elif elevator_door_process_bar[elevator_id] < 3 / 4:
                    self.paint_item(elevator_id, elevator_cur_floor[elevator_id], color, "           等待中")
                else:
                    self.paint_item(elevator_id, elevator_cur_floor[elevator_id], color, "           关门中")
        mutex.unlock()

        # 对外部来说，遍历任务，找出未完成的设为红色，其他设为默认None
        for button in self.external_up_buttons:
            button.setStyleSheet("background-color : None")
        for button in self.external_down_buttons:
            button.setStyleSheet("background-color : None")
        mutex.lock()
        for outer_task in outer_tasks_list:
            if outer_task.task_state != TASK_STATE.FINISHED:
                if outer_task.move_state == MOVE_STATE.UP:  # 注意index
                    self.external_up_buttons[outer_task.floor].setStyleSheet("background-color : yellow")
                elif outer_task.move_state == MOVE_STATE.DOWN:
                    self.external_down_buttons[outer_task.floor].setStyleSheet("background-color : yellow")
        mutex.unlock()

        # 将电梯对应的状态栏涂上色
        mutex.lock()
        for elevator_id in range(ELEVATOR_NUM):
            if elevator_states[elevator_id] != ELEVATOR_STATE.FAULT:
                if elevator_states[elevator_id] != ELEVATOR_STATE.DOOR:
                    if elevator_states[elevator_id] == ELEVATOR_STATE.UP:
                        self.paint_item(elevator_id, elevator_cur_floor[elevator_id], ELEVATOR_COLOR,
                                        "         电梯上升中")
                    elif elevator_states[elevator_id] == ELEVATOR_STATE.DOWN:
                        self.paint_item(elevator_id, elevator_cur_floor[elevator_id], ELEVATOR_COLOR,
                                        "         电梯下降中")
                    else:
                        self.paint_item(elevator_id, elevator_cur_floor[elevator_id], ELEVATOR_COLOR)
                if elevator_cur_floor[elevator_id] > 0:
                    self.paint_item(elevator_id, elevator_cur_floor[elevator_id] - 1)
                if elevator_cur_floor[elevator_id] < 19:
                    self.paint_item(elevator_id, elevator_cur_floor[elevator_id] + 1)
        mutex.unlock()

class Elevator(QThread):
    """
    电梯内部处理线程
    """

    def __init__(self, elevator_id):
        """
        初始化电梯对象
        :param elevator_id: 电梯编号
        """
        super().__init__()
        self.elevator_id = elevator_id
        self.time_slice = 100

    def move_one_floor(self, move_state):
        """
        电梯移动一层楼
        :param move_state: 电梯运行状态（UP/DOWN）
        """
        # 修改电梯运行状态
        if move_state == MOVE_STATE.UP:
            elevator_states[self.elevator_id] = ELEVATOR_STATE.UP
        elif move_state == MOVE_STATE.DOWN:
            elevator_states[self.elevator_id] = ELEVATOR_STATE.DOWN

        # 运行过程
        has_slept_time = 0
        # 模拟上升用时
        while has_slept_time != MOVE_TIME:
            mutex.unlock()

            self.msleep(self.time_slice)
            has_slept_time += self.time_slice
            mutex.lock()

            # 出故障
            if elevator_states[self.elevator_id] == ELEVATOR_STATE.FAULT:
                self.trouble_solving()
                return

        # 该电梯向上/下运行一层
        if move_state == MOVE_STATE.UP:
            elevator_cur_floor[self.elevator_id] += MOVE_STATE.UP.value
        elif move_state == MOVE_STATE.DOWN:
            elevator_cur_floor[self.elevator_id] += MOVE_STATE.DOWN.value
        elevator_states[self.elevator_id] = ELEVATOR_STATE.NORMAL

        # 电梯故障，则进入故障处理
        if elevator_states[self.elevator_id] == ELEVATOR_STATE.FAULT:
            self.trouble_solving()

    def door_operation(self):
        """
        电梯门操作，开门-等待-关门
        """
        # 电梯门用时
        door_open_time = 0
        elevator_states[self.elevator_id] = ELEVATOR_STATE.DOOR
        while True:
            if elevator_states[self.elevator_id] == ELEVATOR_STATE.FAULT:
                self.trouble_solving()
                break
            # 门正在打开
            if elevator_states[self.elevator_id] == ELEVATOR_STATE.DOOR:
                # 开锁，以便别的线程运行
                mutex.unlock()
                self.msleep(self.time_slice)
                door_open_time += self.time_slice
                # 锁回来
                mutex.lock()
                elevator_door_process_bar[self.elevator_id] = door_open_time / DOOR_OPEN_AND_CLOSE_TIME
            # 完成操作
            if elevator_door_process_bar[self.elevator_id] == 1.0:
                # 开关门动作完成
                elevator_states[self.elevator_id] = ELEVATOR_STATE.NORMAL
                # 重新记为0
                elevator_door_process_bar[self.elevator_id] = 0.0
                break

    def trouble_solving(self):
        """
        电梯出现故障，处理措施
        """
        elevator_states[self.elevator_id] = ELEVATOR_STATE.FAULT
        elevator_door_process_bar[self.elevator_id] = 0.0
        for outer_task in outer_tasks_list:
            if outer_task.task_state == TASK_STATE.WAITING:
                # 如果外界的需求恰好与电梯的目的地相符
                if outer_task.floor in elevator_up_target_list[self.elevator_id] or outer_task.floor in \
                        elevator_down_target_list[self.elevator_id]:
                    # 把原先分配给它的任务交给outer重新分配
                    outer_task.task_state = TASK_STATE.UNASSIGNED
        elevator_up_target_list[self.elevator_id] = []
        elevator_down_target_list[self.elevator_id] = []

    def run(self):
        """
         电梯运行线程
        """
        while True:
            mutex.lock()
            if elevator_states[self.elevator_id] == ELEVATOR_STATE.FAULT:
                self.trouble_solving()
                mutex.unlock()
                continue

            # 向上扫描状态
            if elevator_move_states[self.elevator_id] == MOVE_STATE.UP:
                if elevator_up_target_list[self.elevator_id] != []:
                    # 到层开门
                    if elevator_up_target_list[self.elevator_id][0] == elevator_cur_floor[self.elevator_id]:
                        self.door_operation()
                        # 到达以后 把完成的任务删去(分为内外两方面)
                        for outer_task in outer_tasks_list:
                            if outer_task.floor == elevator_cur_floor[self.elevator_id] :
                                outer_task.task_state = TASK_STATE.FINISHED  # 交给outer处理
                                break

                        if elevator_up_target_list != []:
                            elevator_up_target_list[self.elevator_id].pop(0)

                    elif elevator_up_target_list[self.elevator_id][0] > elevator_cur_floor[self.elevator_id]:
                        self.move_one_floor(MOVE_STATE.UP)
                # 当没有上行目标而出现下行目标时 更换状态
                elif elevator_up_target_list[self.elevator_id] == [] and elevator_down_target_list[
                    self.elevator_id] != []:
                    elevator_move_states[self.elevator_id] = MOVE_STATE.DOWN

            # 向下扫描状态时(与上面一致)
            elif elevator_move_states[self.elevator_id] == MOVE_STATE.DOWN:
                if elevator_down_target_list[self.elevator_id] != []:
                    if elevator_down_target_list[self.elevator_id][0] == elevator_cur_floor[self.elevator_id]:
                        self.door_operation()
                        for outer_task in outer_tasks_list:
                            if outer_task.floor == elevator_cur_floor[self.elevator_id]:
                                outer_task.task_state = TASK_STATE.FINISHED
                                break
                        if elevator_down_target_list != []:
                            elevator_down_target_list[self.elevator_id].pop(0)
                    elif elevator_down_target_list[self.elevator_id][0] < elevator_cur_floor[self.elevator_id]:
                        self.move_one_floor(MOVE_STATE.DOWN)
                elif elevator_down_target_list[self.elevator_id] == [] and elevator_up_target_list[
                    self.elevator_id] != []:
                    elevator_move_states[self.elevator_id] = MOVE_STATE.UP

            mutex.unlock()


class Outer(QThread):
    """
    外部任务处理线程
    """

    def __init__(self):
        super().__init__()

    @staticmethod
    def find_best_elevator(outer_task):
        '''
        找到距离最近的电梯编号
        :param outer_task: 外界点击所产生的任务
        :return:
        '''
        min_distance = FLOOR_NUM + 1
        # 初始化分配电梯
        target_id = -1
        # 依次访问每一个电梯
        for i in range(ELEVATOR_NUM):
            # 如果电梯处于故障状态，则跳过它
            if elevator_states[i] == ELEVATOR_STATE.FAULT:
                continue

            # 如果已经上行/下行了，则上/下移动一层
            origin = elevator_cur_floor[i]
            if elevator_states[i] == ELEVATOR_STATE.UP:
                origin += 1
            elif elevator_states[i] == ELEVATOR_STATE.DOWN:
                origin -= 1

            if elevator_move_states[i] == MOVE_STATE.UP:
                targets = elevator_up_target_list[i]
            else:  # down
                targets = elevator_down_target_list[i]

            # 根据到outer_task的距离计算优先级
            # 如果电梯运行方向无任务，则直接算绝对值
            if targets == []:
                distance = abs(origin - outer_task.floor)
            # 若电梯朝着按键所在楼层运行，且运动方向与外部请求相同
            elif elevator_move_states[i] == outer_task.move_state and (
                    (outer_task.move_state == MOVE_STATE.UP and outer_task.floor >= origin) or
                    (outer_task.move_state == MOVE_STATE.DOWN and outer_task.floor <= origin)):
                distance = abs(origin - outer_task.floor)
            # 其余情况则算最远任务楼层到目标楼层的绝对值和最远楼层到当前电梯楼层的绝对值之和
            else:
                distance = abs(origin - targets[-1]) + abs(outer_task.floor - targets[-1])

            # 寻找最小值
            if distance < min_distance:
                min_distance = distance
                target_id = i

        return target_id

    @staticmethod
    def add_task_to_queue(elevator_id, out_task, descending=False):
        '''
        将任务加入相应的队列中
        :param elevator_id: 相应电梯
        :param out_task: 产生的任务
        :param descending: 升序/降序
        :return:
        '''
        target_queue = []
        if descending == True:
            target_queue = elevator_down_target_list[elevator_id]
        else:
            target_queue = elevator_up_target_list[elevator_id]
        if out_task.floor not in target_queue:
            target_queue.append(out_task.floor)
            target_queue.sort(reverse=descending)
            # 设为等待态
            out_task.task_state = TASK_STATE.WAITING

    def run(self):
        while True:
            # 互斥锁
            mutex.lock()
            global outer_tasks_list

            # 找到距离最短的电梯编号..
            for outer_task in outer_tasks_list:
                target_id = -1
                # 如果该外部请求未被分配
                if outer_task.task_state == TASK_STATE.UNASSIGNED:
                    target_id = self.find_best_elevator(outer_task)

                    # 找到了电梯，添加任务到target_id电梯的对应数组下
                    if target_id != -1:
                        # 若该电梯恰好在对应请求楼层，但运行状态与需求状态不同
                        # 或该电梯还未到达该层
                        if (elevator_cur_floor[target_id] == outer_task.floor
                            and outer_task.move_state == MOVE_STATE.UP and elevator_states[
                                target_id] != ELEVATOR_STATE.UP) \
                                or elevator_cur_floor[target_id] < outer_task.floor:
                            self.add_task_to_queue(target_id, outer_task)
                        elif (elevator_cur_floor[target_id] == outer_task.floor
                              and outer_task.move_state == MOVE_STATE.DOWN and elevator_states[
                                  target_id] != ELEVATOR_STATE.DOWN) \
                                or elevator_cur_floor[target_id] > outer_task.floor:
                            self.add_task_to_queue(target_id, outer_task, descending=True)

            # 将已经完成的任务从请求清单上删除
            outer_tasks_list = [task for task in outer_tasks_list if task.task_state != TASK_STATE.FINISHED]

            # 互斥锁打开
            mutex.unlock()


if __name__ == '__main__':

    # 全局变量
    elevator_up_target_list = [[] for _ in range(ELEVATOR_NUM)]  # 每台电梯当前需要向上运行处理的目标有哪些（升序排序）
    elevator_down_target_list = [[] for _ in range(ELEVATOR_NUM)]  # 每台电梯当前需要向下运行处理的目标有哪些（降序排序）
    outer_tasks_list = []  # 外部按钮产生的需求(是OuterTask类的对象)
    elevator_states = [ELEVATOR_STATE.NORMAL for _ in range(ELEVATOR_NUM)]  # 每组电梯的状态
    elevator_cur_floor = [0 for _ in range(ELEVATOR_NUM)]  # 每台电梯的当前楼层
    elevator_door_process_bar = [0.0 for _ in range(ELEVATOR_NUM)]  # 开/关门进度条
    elevator_move_states = [MOVE_STATE.UP for _ in range(ELEVATOR_NUM)]  # 每台电梯当前的扫描运行状态

    # 调整窗口大小
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QtWidgets.QApplication(sys.argv)

    # 展示ui界面
    main_window = MainWindow()

    # 开启外部处理线程
    outer = Outer()
    outer.start()

    # 开启电梯线程
    elevators = [Elevator(i) for i in range(ELEVATOR_NUM)]
    for elevator in elevators:
        elevator.start()

    sys.exit(app.exec_())
