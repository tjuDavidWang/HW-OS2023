import sys
from typing import Optional

import PyQt5
from PyQt5.QtCore import QSize
from PyQt5.Qt import *
import time
import os
import pickle

# 每个物理块大小
blockSize = 512
# 磁盘中物理块个数
blockNum = 512


class Block:
    """
    物理块
    """

    def __init__(self, blockIndex: int, data=""):
        # 物理块的编号
        self.blockIndex = blockIndex
        # 物理块中的数据
        self.data = data

    def write(self, newData: str):
        # 将新数据写入物理块，如果新数据超过物理块的大小，只写入前blockSize个字符
        self.data = newData[:blockSize]
        # 返回未写入的数据
        return newData[blockSize:]

    def read(self):
        # 读取物理块中的数据
        return self.data

    def isFull(self):
        # 判断物理块是否已满
        return len(self.data) == blockSize

    def append(self, newData: str) -> str:
        """
        追加新内容，如果物理块已满，返回无法写入的部分
        """
        remainSpace = blockSize - len(self.data)
        if remainSpace >= len(newData):
            self.data += newData
            return ""
        else:
            self.data += newData[:remainSpace]
            return newData[remainSpace:]

    def clear(self):
        # 清空物理块中的数据
        self.data = ""


class FAT:
    """
    文件分配表（File Allocation Table）
    """

    # 初始化FAT表，所有位置都是空闲的记为-2
    def __init__(self):
        self.fat = []
        for i in range(blockNum):
            self.fat.append(-2)

    # 寻找FAT表中的一个空闲位置
    def findBlank(self):
        for i in range(blockNum):
            if self.fat[i] == -2:
                return i
        return -1

    # 将数据写入磁盘，寻找空闲的空间，并更新FAT表
    def write(self, data, disk):
        start = -1
        cur = -1

        while data != "":
            newLoc = self.findBlank()
            if newLoc == -1:
                raise Exception(print('磁盘空间不足!'))
                return
            if cur != -1:
                self.fat[cur] = newLoc
            else:
                start = newLoc
            cur = newLoc
            data = disk[cur].write(data)
            self.fat[cur] = -1

        return start

    # 删除从某个位置开始的所有数据，并清空对应的FAT表项
    def delete(self, start, disk):
        if start == -1:
            return

        while self.fat[start] != -1:
            disk[start].clear()
            las = self.fat[start]
            self.fat[start] = -2
            start = las

        self.fat[start] = -2
        disk[start].clear()

    # 更新从某个位置开始的所有数据，首先删除原有数据，然后写入新的数据
    def update(self, start, data, disk):
        self.delete(start, disk)
        return self.write(data, disk)

    # 读取从某个位置开始的所有数据
    def read(self, start, disk):
        data = ""
        while self.fat[start] != -1:
            data += disk[start].read()
            start = self.fat[start]
        data += disk[start].read()
        return data

    # 获得已经使用的块所占的百分比
    def get_usage_percentage(self):
        # 计算已经被占用的块的数量
        used_blocks = sum(1 for block in self.fat if block != -2)
        # 计算总的块的数量
        total_blocks = len(self.fat)
        # 计算并返回空间占用的百分比
        return (used_blocks / total_blocks) * 100


class FCB:
    """
    文件控制块（File Control Block）
    """

    def __init__(self, name, createTime, data, fat, disk):
        # 文件名
        self.name = name
        # 创建时间
        self.createTime = createTime
        # 最后修改时间
        self.updateTime = self.createTime

        # 根据data为其分配空间
        self.start = -1

    # 更新文件内容，调用FAT的update方法
    def update(self, newData, fat, disk):
        """
        更新文件内容
        """
        self.start = fat.update(self.start, newData, disk)

    # 删除文件，调用FAT的delete方法
    def delete(self, fat, disk):
        """
        删除文件
        """
        fat.delete(self.start, disk)

    # 读取文件内容，调用FAT的read方法
    def read(self, fat, disk):
        if self.start == -1:
            return ""
        else:
            return fat.read(self.start, disk)


class Catalog:
    """
    多级目录结点
    """

    def __init__(self, name, isFile, fat, disk, createTime, parent=None, data=""):
        # 结点的名称
        self.name = name
        # 结点是否为文件类型
        self.isFile = isFile
        # 结点的父结点
        self.parent = parent
        # 结点的创建时间
        self.createTime = createTime
        # 结点的最后更新时间
        self.updateTime = createTime

        # 如果结点是文件夹类型
        if not self.isFile:
            # 存储子结点的列表
            self.children = []
        # 如果结点是文件类型，创建一个FCB来存储文件数据
        else:
            self.data = FCB(name, createTime, data, fat, disk)


# 编辑栏
class EditingInterface(QWidget):
    _signal = PyQt5.QtCore.pyqtSignal(str)

    def __init__(self, name, data):
        super().__init__()
        self.resize(1200, 800)
        self.setWindowTitle(name)
        self.name = name
        self.setWindowIcon(QIcon('img/file.png'))

        self.resize(412, 412)
        self.text_edit = QTextEdit(self)  # 实例化一个QTextEdit对象
        self.text_edit.setText(data)  # 设置编辑框初始化时显示的文本
        self.text_edit.setPlaceholderText("在此输入文件内容")  # 设置占位字符串
        self.text_edit.textChanged.connect(self.changeMessage)  # 判断文本是否发生改变
        self.initialData = data

        self.h_layout = QHBoxLayout()
        self.v_layout = QVBoxLayout()

        self.v_layout.addWidget(self.text_edit)
        self.v_layout.addLayout(self.h_layout)

        self.setLayout(self.v_layout)

        # self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setWindowModality(PyQt5.QtCore.Qt.ApplicationModal)
        # self.statusBar().showMessage('共'+str(len(self.text_edit.toPlainText()))+'字')

    def closeEvent(self, event):
        # 如果打开后没有修改，则直接关闭即可
        if self.initialData == self.text_edit.toPlainText():
            event.accept()
            return

        reply = QMessageBox()
        reply.setWindowTitle('提醒')
        reply.setIcon(QMessageBox.Warning)
        reply.setWindowIcon(QIcon("img/folder.png"))
        reply.setText('您想将其保存到 "' + self.name + '" 吗？')
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No | QMessageBox.Ignore)
        buttonY = reply.button(QMessageBox.Yes)
        buttonY.setText('保存')
        buttonN = reply.button(QMessageBox.No)
        buttonN.setText('不保存')
        buttonI = reply.button(QMessageBox.Ignore)
        buttonI.setText('取消')

        reply.exec_()

        if reply.clickedButton() == buttonI:
            event.ignore()
        elif reply.clickedButton() == buttonY:
            self._signal.emit(self.text_edit.toPlainText())
            event.accept()
        else:
            event.accept()

    def changeMessage(self):
        # self.statusBar().showMessage('共'+str(len(self.text_edit.toPlainText()))+'字')
        pass

    def button_slot(self, button):
        if button == self.save_button:
            choice = QMessageBox.question(self, "Question", "Do you want to save it?", QMessageBox.Yes | QMessageBox.No)
            if choice == QMessageBox.Yes:
                with open('First text.txt', 'w') as f:
                    f.write(self.text_edit.toPlainText())
                self.close()
            elif choice == QMessageBox.No:
                self.close()
        elif button == self.clear_button:
            self.text_edit.clear()


# 属性栏
class AttributeInterface(QWidget):
    def __init__(self, name, isFile, createTime, updateTime, child=0):
        super().__init__()
        self.setWindowTitle('属性')
        self.setWindowIcon(QIcon('img/attribute.png'))

        # 创建一个选项卡小部件
        self.tabs = QTabWidget(self)

        # 创建一个选项卡
        self.tab = QWidget()
        self.tabs.addTab(self.tab, "详细信息")

        # 设置选项卡的布局
        self.tab.layout = QFormLayout(self)

        # 文件名
        name_icon = QLabel()
        name_label = QLabel(name)
        if isFile:
            pixmap = QPixmap('img/file.png')
        else:
            pixmap = QPixmap('img/folder.png')

        # 调整图像大小
        scaled_pixmap = pixmap.scaled(72, 72, Qt.KeepAspectRatio)
        name_icon.setPixmap(scaled_pixmap)

        # 创建一个水平布局并添加图标和名称
        name_layout = QHBoxLayout()
        name_layout.addWidget(name_icon)
        name_layout.addWidget(name_label)
        name_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.tab.layout.addRow(name_layout)

        # 创建时间
        self.tab.layout.addRow("创建时间:", QLabel(self.format_time(createTime)))

        # 更新时间
        if isFile:
            self.tab.layout.addRow("修改时间:", QLabel(self.format_time(updateTime)))
        else:
            self.tab.layout.addRow("内部项目:", QLabel(str(child)))

        self.tab.setLayout(self.tab.layout)

        # 设置主布局
        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.tabs)
        self.setLayout(self.layout)

    def format_time(self, t):
        return f"{t.tm_year}年{t.tm_mon}月{t.tm_mday}日 {t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}"


# 列表
class ListWidget(QListWidget):
    def __init__(self, curNode, parents, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # 拖拽设置
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)  # 设置拖放
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)  # 设置选择多个
        self.setDefaultDropAction(Qt.CopyAction)
        # 双击可编辑
        self.edited_item = self.currentItem()
        self.close_flag = True
        self.currentItemChanged.connect(self.close_edit)
        # 当前目录
        self.curNode = curNode
        # 父亲
        self.parents = parents
        # 正在被编辑状态
        self.isEdit = False

    def keyPressEvent(self, e: QKeyEvent) -> None:
        """回车事件，关闭edit"""
        super().keyPressEvent(e)
        if e.key() == Qt.Key_Return:
            if self.close_flag:
                self.close_edit()
            self.close_flag = True

    def edit_new_item(self) -> None:
        self.close_flag = False
        self.close_edit()
        count = self.count()
        self.addItem('')
        item = self.item(count)
        self.edited_item = item
        self.openPersistentEditor(item)
        self.editItem(item)

    def item_double_clicked(self, modelindex: QModelIndex) -> None:
        # 禁用
        return

    def editLast(self, index=-1) -> None:
        self.close_edit()
        item = self.item(self.count() - 1)
        self.setCurrentItem(item)
        self.edited_item = item
        self.openPersistentEditor(item)
        self.editItem(item)
        self.isEdit = True
        self.index = index

    def editSelected(self, index) -> None:
        self.close_edit()
        item = self.selectedItems()[-1]
        self.setCurrentItem(item)
        self.edited_item = item
        self.openPersistentEditor(item)
        self.editItem(item)
        self.isEdit = True
        self.index = index

    def close_edit(self, *_) -> None:
        if self.edited_item:
            self.isEdit = False
            self.closePersistentEditor(self.edited_item)
            # 检验是否重名
            while True:
                sameName = False
                for i in range(len(self.curNode.children) - 1):
                    if self.edited_item.text() == self.curNode.children[i].name and self.index != i:
                        self.edited_item.setText(self.edited_item.text() + "(2)")
                        sameName = True
                        break
                if not sameName:
                    break

            # 计算item在其父结点的下标

            self.curNode.children[self.index].name = self.edited_item.text()
            # 更新父目录
            self.parents.update_tree()

            self.edited_item = None

    def dragEnterEvent(self, e: QDragEnterEvent) -> None:
        if e.mimeData().hasText():
            if e.mimeData().text().startswith('file:///'):
                e.accept()
        else:
            e.ignore()

    def dragMoveEvent(self, e: QDragMoveEvent) -> None:
        e.accept()

    def dropEvent(self, e: QDropEvent) -> None:
        paths = e.mimeData().text().split('\n')
        for path in paths:
            path = path.strip()
            if len(path) > 8:
                self.addItem(path.strip()[8:])
        e.accept()


# 主要逻辑实现
class FileSystem(QMainWindow):

    def __init__(self):
        super().__init__()

        # 读取外存中内容
        self.project_init()

        # 设置根目录为目录的第一个元素
        self.curNode = self.catalog[0]
        self.rootNode = self.curNode
        self.baseUrl = ['root']
        self.lastLoc = -1  # 以便于返回上层目录
        # 初始化
        self.init_ui()

    # 初始化ui界面
    def init_ui(self):

        def set_window_features():
            # 设置窗口的大小、标题、图标
            self.resize(1200, 800)
            self.setWindowTitle('文件资源管理器')
            self.setWindowIcon(QIcon('img/folder.ico'))

            # 使窗口居中显示
            window_geometry = self.frameGeometry()
            center_point = QDesktopWidget().availableGeometry().center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())

            # 窗口布局
            self.grid = QGridLayout()
            self.grid.setSpacing(10)
            self.widGet = QWidget()
            self.widGet.setLayout(self.grid)
            self.setCentralWidget(self.widGet)

        def set_menu():
            # 菜单栏
            menubar = self.menuBar()
            menubar.addAction('格式化', self.format)

        def set_toolbar():
            # 添加工具栏
            self.tool_bar = self.addToolBar('工具栏')

            # 返回键
            self.back_action = QAction(QIcon('img/back.png'), '&返回', self)
            self.back_action.setShortcut('Backspace')
            self.back_action.triggered.connect(self.backward)
            self.tool_bar.addAction(self.back_action)
            self.back_action.setEnabled(False)

            # 前进键
            self.forward_action = QAction(QIcon('img/forward.png'), '&前进', self)
            self.forward_action.triggered.connect(self.forward)
            self.tool_bar.addAction(self.forward_action)
            self.forward_action.setEnabled(False)
            self.tool_bar.addSeparator()

            # 当前所在路径
            self.cur_address = QLineEdit()
            self.cur_address.setText(' > root')
            self.cur_address.setReadOnly(True)
            self.cur_address.addAction(QIcon('img/folder.png'), QLineEdit.LeadingPosition)
            self.cur_address.setMinimumHeight(40)

            # 修改布局
            ptrLayout = QFormLayout()
            ptrLayout.addRow(self.cur_address)
            ptrWidget = QWidget()
            ptrWidget.setLayout(ptrLayout)
            ptrWidget.adjustSize()
            self.tool_bar.addWidget(ptrWidget)
            self.tool_bar.setMovable(False)

        def set_navigation_bar():
            # 设置一个地址树部件
            self.tree = QTreeWidget()
            # 设置标题
            self.tree.setHeaderLabels(['快速访问'])
            # 设置列数
            self.tree.setColumnCount(1)
            # 建树
            self.build_tree()
            # 设置初始状态
            self.tree.setCurrentItem(self.rootItem)
            self.treeItem = [self.rootItem]

            # 绑定单击事件
            self.tree.itemClicked['QTreeWidgetItem*', 'int'].connect(self.click_item)
            # 将其位置绑定在第2行的第一列
            self.grid.addWidget(self.tree, 1, 0)

        def set_file_info():
            self.listView = ListWidget(self.curNode, parents=self)
            self.listView.setMinimumWidth(800)
            self.listView.setViewMode(QListView.IconMode)
            self.listView.setIconSize(QSize(72, 72))
            self.listView.setGridSize(QSize(100, 100))
            self.listView.setResizeMode(QListView.Adjust)
            self.listView.setMovement(QListView.Static)
            self.listView.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.listView.doubleClicked.connect(self.open_file)

            # 加载当前路径文件
            self.load_cur_address()

            # 加载右击菜单
            self.listView.setContextMenuPolicy(Qt.CustomContextMenu)
            self.listView.customContextMenuRequested.connect(self.show_menu)

            # 将其位置绑定在第2行的第2列
            self.grid.addWidget(self.listView, 1, 1)

            # 建立一个进度条，观察空间使用情况
            self.progress_bar = QProgressBar(self)
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.grid.addWidget(self.progress_bar, 2, 0, 1, 2)
            self.progress_bar.setValue(int(self.fat.get_usage_percentage() * 100))

            # 删除文件快捷键
            QShortcut(QKeySequence(self.tr("Delete")), self, self.delete)

        # 定义窗体相关特性
        set_window_features()

        # 设置菜单栏
        set_menu()

        # 设置工具栏
        set_toolbar()

        # 设置地址树
        set_navigation_bar()

        # 设置文件基本信息
        set_file_info()
        # 美化
        self.update_address_bar()

    # 读取外存中内容
    def project_init(self):
        # 读取fat表
        if not os.path.exists('fat'):
            self.fat = FAT()
            self.fat.fat = [-2] * blockNum
            # 存储fat表
            with open('fat', 'wb') as f:
                f.write(pickle.dumps(self.fat))
        else:
            with open('fat', 'rb') as f:
                self.fat = pickle.load(f)

        # 读取disk表
        if not os.path.exists('disk'):
            self.disk = []
            for i in range(blockNum):
                self.disk.append(Block(i))
            # 存储disk表
            with open('disk', 'wb') as f:
                f.write(pickle.dumps(self.disk))
        else:
            with open('disk', 'rb') as f:
                self.disk = pickle.load(f)

        # 读取catalog表
        if not os.path.exists('catalog'):
            self.catalog = []
            self.catalog.append(Catalog("root", False, self.fat, self.disk, time.localtime(time.time())))
            # 存储
            with open('catalog', 'wb') as f:
                f.write(pickle.dumps(self.catalog))
        else:
            with open('catalog', 'rb') as f:
                self.catalog = pickle.load(f)

    # 建树
    def build_tree(self):
        self.tree.clear()

        # 内部函数，用于递归构建树
        def buildTreeRecursive(node: Catalog, parent: QTreeWidgetItem):
            """
            目录树的建立
            """
            child = QTreeWidgetItem(parent)
            child.setText(0, node.name)

            if node.isFile:
                child.setIcon(0, QIcon('img/file.png'))
            else:
                if len(node.children) == 0:
                    child.setIcon(0, QIcon('img/folder.png'))
                else:
                    child.setIcon(0, QIcon('img/folderWithFile.png'))
                for i in node.children:
                    buildTreeRecursive(i, child)

            return child

        self.rootItem = buildTreeRecursive(self.catalog[0], self.tree)
        # 加载根节点的所有子控件
        self.tree.addTopLevelItem(self.rootItem)
        self.tree.expandAll()

    # 格式化页面
    def format(self):
        # 结束编辑
        self.listView.close_edit()

        # 提示框
        reply = QMessageBox()
        reply.setWindowIcon(QIcon("img/folder.png"))
        reply.setWindowTitle('提醒')
        reply.setIcon(QMessageBox.Warning)
        reply.setText('确定要格式化磁盘？')
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        buttonY = reply.button(QMessageBox.Yes)
        buttonY.setText('确定')
        buttonN = reply.button(QMessageBox.No)
        buttonN.setText('取消')
        reply.exec_()
        reply.show()

        if reply.clickedButton() == buttonN:
            return

        # 格式化文件
        # 将FAT清空，初始化
        self.fat = FAT()
        self.fat.fat = [-2] * blockNum
        with open('fat', 'wb') as f:
            f.write(pickle.dumps(self.fat))

        # 清空磁盘disk
        self.disk = []
        for i in range(blockNum):
            self.disk.append(Block(i))
        with open('disk', 'wb') as f:
            f.write(pickle.dumps(self.disk))

        # 清空目录
        self.catalog = []
        self.catalog.append(Catalog("root", False, self.fat, self.disk, time.localtime(time.time())))
        with open('catalog', 'wb') as f:
            f.write(pickle.dumps(self.catalog))

        # 重新加载页面
        self.hide()
        self.main_window = FileSystem()
        self.main_window.show()

        self.update_tree()

    # 点击树点跳转
    def click_item(self, item, column):
        ways = [item]
        # 将切换跳转路径打印出来
        temp = item
        while temp.parent() is not None:
            temp = temp.parent()
            ways.append(temp)
        ways.reverse()
        # 回退到根节点
        while self.backward():
            pass
        # 将路径和路径树都作为根节点
        self.baseUrl = self.baseUrl[:1]
        self.treeItem = self.treeItem[:1]

        # 一步一步前进获得寻址路径
        for i in ways:
            if i == self.rootItem:
                continue
            # 前往该路径
            # 从curNode中查询item
            newNode = next((j for j in self.curNode.children if j.name == i.text(0)), None)
            # 前往路径j
            if newNode is not None and not newNode.isFile:
                self.curNode = newNode
                # 更新当前位置
                self.load_cur_address()
                self.listView.curNode = self.curNode
                self.baseUrl.append(newNode.name)

                # 更新路径
                selectedItem = next((self.treeItem[-1].child(j) for j in range(self.treeItem[-1].childCount()) if
                                     self.treeItem[-1].child(j).text(0) == newNode.name), None)
                if selectedItem is not None:
                    self.treeItem.append(selectedItem)
                    self.tree.setCurrentItem(selectedItem)
                else:
                    break

        # 更新地址栏内容
        self.update_address_bar()
        # 设置回退/前进键的可用状态
        self.back_action.setEnabled(self.curNode != self.rootNode)
        self.forward_action.setEnabled(False)
        # 将上一次的位置记为lastLoc
        self.lastLoc = -1

    # 打开文件
    def open_file(self, modelindex: QModelIndex) -> None:
        # 关闭可能正在进行的文件编辑
        self.listView.close_edit()

        try:
            # 尝试获取用户点击的项目
            item = self.listView.item(modelindex.row())
        except:
            # 如果出错，可能是因为用户使用了右键打开菜单
            # 如果没有选中的项目，直接返回
            if len(self.listView.selectedItems()) == 0:
                return
            # 否则，获取最后一个选中的项目
            item = self.listView.selectedItems()[-1]

        # 如果可以前进（即lastLoc不等于-1），并且nextStep为True
        if self.lastLoc != -1 and self.nextStep:
            # 获取lastLoc对应的项目，并重置lastLoc和nextStep
            item = self.listView.item(self.lastLoc)
            self.lastLoc = -1
            self.forward_action.setEnabled(False)
        self.nextStep = False

        # 在当前节点的子节点中查找与项目名称相同的节点
        newNode = None
        for i in self.curNode.children:
            if i.name == item.text():
                newNode = i
                break

        # 内部函数，用于获取数据并向文件中写入新数据
        def getData(parameter):
            """
            向文件中写入新数据
            """
            newNode.data.update(parameter, self.fat, self.disk)
            newNode.updateTime = time.localtime(time.time())

        # 如果找到的节点是文件
        if newNode.isFile:
            # 读取文件数据，并打开一个编辑窗口显示文件内容
            data = newNode.data.read(self.fat, self.disk)
            self.child = EditingInterface(newNode.name, data)
            self.child._signal.connect(getData)
            self.child.show()
            self.writeFile = newNode
        # 如果找到的节点是目录(文件夹)
        else:
            # 关闭可能正在进行的文件编辑
            self.listView.close_edit()

            # 更新当前节点，并加载新节点的文件
            self.curNode = newNode
            self.load_cur_address()
            self.listView.curNode = self.curNode

            # 更新当前路径
            self.baseUrl.append(newNode.name)

            # 在树状视图中找到新节点对应的项目，并设置为当前项目
            for i in range(self.treeItem[-1].childCount()):
                if self.treeItem[-1].child(i).text(0) == newNode.name:
                    selectedItem = self.treeItem[-1].child(i)
            self.treeItem.append(selectedItem)
            self.tree.setCurrentItem(selectedItem)
            self.back_action.setEnabled(True)

            # 更新地址栏
            self.update_address_bar()

        self.update_tree()

    # 返回上一级
    def backward(self):
        self.listView.close_edit()

        if self.rootNode == self.curNode:
            # 根节点无法返回
            return False

        # 记录上次所在位置
        for i in range(len(self.curNode.parent.children)):
            if self.curNode.parent.children[i].name == self.curNode.name:
                self.lastLoc = i
                self.forward_action.setEnabled(True)
                break

        self.curNode = self.curNode.parent
        # 更新当前位置
        self.load_cur_address()
        self.listView.curNode = self.curNode

        self.baseUrl.pop()
        self.treeItem.pop()
        self.tree.setCurrentItem(self.treeItem[-1])
        self.update_tree()
        self.update_address_bar()

        if self.curNode == self.rootNode:
            self.back_action.setEnabled(False)

        return True

    # 跳转下一级
    def forward(self):
        self.nextStep = True
        self.open_file(QModelIndex())

    # 更新地址栏
    def update_address_bar(self):
        self.statusBar().showMessage(str(len(self.curNode.children)) + '个项目')
        s = '> root'
        for i, item in enumerate(self.baseUrl):
            if i == 0:
                continue
            s += " > " + item
        self.cur_address.setText(s)
        self.update_tree()

    # 重命名
    def rename(self):
        if len(self.listView.selectedItems()) == 0:
            return
        # 获取最后一个被选中的
        self.listView.editSelected(self.listView.selectedIndexes()[-1].row())
        self.update_tree()

    # 删除文件/文件夹
    def delete(self):
        if len(self.listView.selectedItems()) == 0:
            return

        item = self.listView.selectedItems()[-1]
        index = self.listView.selectedIndexes()[-1].row()

        # 提示框
        reply = QMessageBox()
        reply.setIcon(QMessageBox.Warning)
        reply.setWindowIcon(QIcon("img/folder.ico"))
        reply.setWindowTitle('提醒')
        # 不同的提醒
        if self.curNode.children[index].isFile:
            reply.setText('确定要删除文件 "' + item.text() + '" 吗？')
        else:
            reply.setText('确定要删除文件夹 "' + item.text() + '" 及其内部所有内容吗？')
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        buttonY = reply.button(QMessageBox.Yes)
        buttonY.setText('确定')
        buttonN = reply.button(QMessageBox.No)
        buttonN.setText('取消')

        reply.exec_()

        if reply.clickedButton() == buttonN:
            return

        # 删除文件
        self.listView.takeItem(index)
        del item

        # 内部函数，用于递归删除文件
        def deleteFileRecursive(node):
            if node.isFile:
                node.data.delete(self.fat, self.disk)
            else:
                for i in node.children:
                    deleteFileRecursive(i)

        # 删除fat表中的内容
        deleteFileRecursive(self.curNode.children[index])
        self.curNode.children.remove(self.curNode.children[index])

        # 内部函数，用于更新目录表
        def updateCatalog(node):
            if node.isFile:
                return [node]
            else:
                x = [node]
                for i in node.children:
                    x += updateCatalog(i)
                return x

        # 更新catalog表
        self.catalog = updateCatalog(self.rootNode)

        # 更新
        self.update_tree()

    # 创建文件夹
    def create_folder(self):

        self.item_1 = QListWidgetItem(QIcon("img/folder.png"), "新建文件夹")
        self.listView.addItem(self.item_1)
        self.listView.editLast()

        # 添加到目录表中
        newNode = Catalog(self.item_1.text(), False, self.fat, self.disk, time.localtime(time.time()), self.curNode)
        self.curNode.children.append(newNode)
        self.catalog.append(newNode)

        # 更新树
        self.update_tree()

    # 创建文件
    def create_file(self):
        self.item_1 = QListWidgetItem(QIcon("img/file.png"), "新建文件")
        self.listView.addItem(self.item_1)
        self.listView.editLast()

        # 添加到目录表中
        newNode = Catalog(self.item_1.text(), True, self.fat, self.disk, time.localtime(time.time()), self.curNode)
        self.curNode.children.append(newNode)
        self.catalog.append(newNode)

        # 更新树
        self.update_tree()

    # 右击项目，展示菜单
    def show_menu(self, point):
        # 创建一个菜单，并将其关联到列表视图
        menu = QMenu(self.listView)

        # 展示其属性
        def viewAttribute():
            # 查看当前路径属性
            if len(self.listView.selectedItems()) == 0:
                self.child = AttributeInterface(self.curNode.name, False, self.curNode.createTime,
                                                self.curNode.updateTime,
                                                len(self.curNode.children))

                self.child.show()
                return
            else:
                # 获取选中的最后一个
                node = self.curNode.children[self.listView.selectedIndexes()[-1].row()]
                if node.isFile:
                    self.child = AttributeInterface(node.name, node.isFile, node.createTime, node.updateTime, 0)
                else:
                    self.child = AttributeInterface(node.name, node.isFile, node.createTime, node.updateTime,
                                                    len(node.children))
                self.child.show()
                return

        # 如果用户选中元素
        if len(self.listView.selectedItems()) != 0:
            # 创建打开文件的操作
            action_open_file = QAction(QIcon('img/open.png'), '打开')
            action_open_file.triggered.connect(self.open_file)
            menu.addAction(action_open_file)

            # 创建删除文件的操作
            action_delete_file = QAction(QIcon('img/delete.png'), '删除')
            action_delete_file.triggered.connect(self.delete)
            menu.addAction(action_delete_file)

            # 创建重命名文件的操作
            action_rename_file = QAction(QIcon('img/rename.png'), '重命名')
            action_rename_file.triggered.connect(self.rename)
            menu.addAction(action_rename_file)

            # 创建查看属性的操作
            action_view_attributes = QAction(QIcon('img/attribute.png'), '属性')
            action_view_attributes.triggered.connect(viewAttribute)
            menu.addAction(action_view_attributes)


        # 用户没选中元素(即右键空白处)
        else:
            # 创建查看菜单
            viewMenu = QMenu(menu)
            viewMenu.setTitle('查看')
            viewMenu.setIcon(QIcon('img/view.png'))

            def set_icon_and_grid_size(icon_size, grid_size):
                # 设置图标和网格的大小
                self.listView.setIconSize(QSize(icon_size, icon_size))
                self.listView.setGridSize(QSize(grid_size, grid_size))

            # 创建大图标的操作
            bigIconAction = QAction(QIcon('img/view_big.png'), '大图标')
            bigIconAction.triggered.connect(lambda: set_icon_and_grid_size(172, 200))
            viewMenu.addAction(bigIconAction)

            # 创建中图标的操作
            middleIconAction = QAction(QIcon('img/view_medium.png'), '中等图标')
            middleIconAction.triggered.connect(lambda: set_icon_and_grid_size(72, 100))
            viewMenu.addAction(middleIconAction)

            # 创建小图标的操作
            smallIconAction = QAction(QIcon('img/view_small.png'), '小图标')
            smallIconAction.triggered.connect(lambda: set_icon_and_grid_size(56, 84))
            viewMenu.addAction(smallIconAction)

            menu.addMenu(viewMenu)

            # 创建新建菜单
            createMenu = QMenu(menu)
            createMenu.setTitle('新建')
            createMenu.setIcon(QIcon('img/create.png'))

            # 创建新建文件夹的操作
            createFolderAction = QAction(QIcon('img/folder.png'), '文件夹')
            createFolderAction.triggered.connect(self.create_folder)
            createMenu.addAction(createFolderAction)

            # 创建新建文件的操作
            createFileAction = QAction(QIcon('img/file.png'), '文件')
            createFileAction.triggered.connect(self.create_file)
            createMenu.addAction(createFileAction)

            menu.addMenu(createMenu)

            # 创建查看属性的操作
            action_view_attributes = QAction(QIcon('img/attribute.png'), '属性')
            action_view_attributes.triggered.connect(viewAttribute)
            menu.addAction(action_view_attributes)

        # 显示菜单
        dest_point = self.listView.mapToGlobal(point)
        menu.exec_(dest_point)

    # 更新文件列表
    def update_tree(self):
        node = self.rootNode
        item = self.rootItem

        # 内部函数，用于递归更新树
        def updateTreeRecursive(node: Catalog, item: QTreeWidgetItem):
            item.setText(0, node.name)
            if node.isFile:
                item.setIcon(0, QIcon('img/file.png'))
            else:
                # 根据是否有子树设置图标
                if len(node.children) == 0:
                    item.setIcon(0, QIcon('img/folder.png'))
                else:
                    item.setIcon(0, QIcon('img/folder.png'))
                if item.childCount() < len(node.children):
                    # 增加一个新item即可
                    child = QTreeWidgetItem(item)
                elif item.childCount() > len(node.children):
                    # 一个一个找，删除掉对应元素
                    for i in range(item.childCount()):
                        if i == item.childCount() - 1:
                            item.removeChild(item.child(i))
                            break
                        if item.child(i).text(0) != node.children[i].name:
                            item.removeChild(item.child(i))
                            break
                for i in range(len(node.children)):
                    updateTreeRecursive(node.children[i], item.child(i))

        # 增加一个新item即可
        if item.childCount() < len(node.children):
            child = QTreeWidgetItem(item)
        # 删除掉对应元素
        elif item.childCount() > len(node.children):
            for i in range(item.childCount()):
                if i == item.childCount() - 1:
                    item.removeChild(item.child(i))
                    break
                if item.child(i).text(0) != node.children[i].name:
                    item.removeChild(item.child(i))
                    break
        # 更新根节点对应的数据
        for i in range(len(node.children)):
            updateTreeRecursive(node.children[i], item.child(i))

        updateTreeRecursive(node, item)
        # 更新空间占用条
        self.progress_bar.setValue(int(self.fat.get_usage_percentage() * 100))

    # 加载当前文件路径
    def load_cur_address(self):
        self.listView.clear()

        for i in self.curNode.children:
            if i.isFile:
                self.item_1 = QListWidgetItem(QIcon("img/file.png"), i.name)
                self.listView.addItem(self.item_1)
            else:
                if len(i.children) == 0:
                    self.item_1 = QListWidgetItem(QIcon("img/folder.png"), i.name)
                else:
                    self.item_1 = QListWidgetItem(QIcon("img/folder.png"), i.name)
                self.listView.addItem(self.item_1)

    # 关闭程序前的询问Catalog
    def closeEvent(self, event):
        # 结束编辑
        self.listView.close_edit()

        reply = QMessageBox()
        reply.setWindowTitle('提醒')
        reply.setWindowIcon(QIcon("img/folder.png"))
        reply.setIcon(QMessageBox.Warning)
        reply.setText('您是否需要将本次操作写入磁盘？')
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.Ignore | QMessageBox.No)
        buttonY = reply.button(QMessageBox.Yes)
        buttonY.setText('写入')
        buttonN = reply.button(QMessageBox.No)
        buttonN.setText('取消')
        buttonI = reply.button(QMessageBox.Ignore)
        buttonI.setText('不写入')

        reply.exec_()

        if reply.clickedButton() == buttonI:
            event.accept()
        elif reply.clickedButton() == buttonY:
            # 将内存中的文件存到本地
            # 存储fat表
            with open('fat', 'wb') as f:
                f.write(pickle.dumps(self.fat))
            # 存储disk表
            with open('disk', 'wb') as f:
                f.write(pickle.dumps(self.disk))
            # 存储
            with open('catalog', 'wb') as f:
                f.write(pickle.dumps(self.catalog))

            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    app = QApplication(sys.argv)

    mainform = FileSystem()

    mainform.show()

    sys.exit(app.exec_())
