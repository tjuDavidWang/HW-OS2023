// 页面
class Page {
    constructor(id) {
        this.id = id;
        this.instructions = Array.from({ length: 10 }, (_, i) => id * 10 + i);
    }
}

//内存块
class Memory {
    constructor(size, method) {
        this.size = size;
        this.method = method || 'FIFO';
        this.frames = [];
        this.lastUsedTime = [0, 0, 0, 0];
    }

    setMethod(method) {
        this.method = method;
    }

    hasInstruction(instruction, time = 0) {
        let pageIndex = this.frames.findIndex(page => page.instructions.includes(instruction));
        if (pageIndex !== -1) {
            if (this.method === 'LRU') {
                this.lastUsedTime[pageIndex] = time;
            }
            return true;
        }
        return false;
    }
}

//生成符合题目要求的指令序列
function generateInstructionSequence() {
    console.log("generateInstructionSequence")
    let instructions = Array.from({ length: 320 }, (_, i) => i);

    // 用于存储执行顺序的数组
    let executionOrder = [];

    // 记录执行的次数
    let count = 0;

    // 当执行的次数小于320时，继续循环
    while (count < 320) {
        // 随机生成一个介于0-319的整数，表示指令编号
        let m = Math.floor(Math.random() * 320);

        // 将这个指令的编号加入执行顺序数组
        executionOrder.push(m);
        count++;

        // 如果存在编号为m+1的指令，则执行这个指令
        if (m + 1 < 320) {
            executionOrder.push(m + 1);
            count++;
        }

        // 如果m大于0，即存在可以跳转的前地址部分的指令
        if (m > 0 && count < 320) {
            // 在0到m-1之间随机选择一个指令
            let m1 = Math.floor(Math.random() * m);

            // 执行这个指令
            executionOrder.push(m1);
            count++;

            // 如果存在编号为m1+1的指令，则执行这个指令
            if (m1 + 1 < m) {
                executionOrder.push(m1 + 1);
                count++;
            }
        }

        // 如果存在可以跳转的后地址部分的指令
        if (m + 2 < 320 && count < 320) {
            // 在m+2到319之间随机选择一个指令
            let m2 = m + 2 + Math.floor(Math.random() * (319 - m - 1));

            // 执行这个指令
            executionOrder.push(m2);
            count++;

            // 如果存在编号为m2+1的指令，则执行这个指令
            if (m2 + 1 < 320) {
                executionOrder.push(m2 + 1);
                count++;
            }
        }
    }
    if (executionOrder.length > 320) { executionOrder.pop(); }
    // 返回执行顺序数组
    return executionOrder;
}

function addInstructionToTable(Id, instructionId, memory, isPageFault, insertedBlock, removedPage) {
    // 获取表格元素
    var table = document.getElementById('memory_table');

    // 创建一个新的行元素
    var row = document.createElement('tr');
    var block1 = (memory.frames[0] === undefined ? "-" : memory.frames[0].id.toString());
    var block2 = (memory.frames[1] === undefined ? "-" : memory.frames[1].id.toString());
    var block3 = (memory.frames[2] === undefined ? "-" : memory.frames[2].id.toString());
    var block4 = (memory.frames[3] === undefined ? "-" : memory.frames[3].id.toString());

    var insertBlock = (insertedBlock === null ? "-" : (insertedBlock + 1).toString());
    var removePage = (removedPage === null ? "-" : removedPage.toString());

    // 创建并添加数据到新的单元格
    var data = [Id, instructionId, block1, block2, block3, block4, isPageFault, insertBlock, removePage];
    for (let i = 0; i < data.length; i++) {
        var cell = document.createElement('td');
        cell.textContent = data[i];

        // 根据条件为单元格添加相应的CSS类
        if (isPageFault === "是") {
            cell.classList.add('miss-cell');
        } else if (isPageFault === "否") {
            cell.classList.add('dismiss-cell');
        }
        if (insertBlock !== "-") {
            if (i === (insertedBlock + 2)) { // 第8列对应插入的块
                cell.classList.add('change-cell');
            }
        }
        row.appendChild(cell);
    }

    // 将新行添加到表格
    table.appendChild(row);
}

function clearMemoryTable() {
    // 获取表格元素
    var table = document.getElementById('memory_table');

    // 移除所有行
    // 移除除了表头以外的所有行
    var rowCount = table.rows.length;
    for (var i = rowCount - 1; i > 0; i--) {
        table.deleteRow(i);
    }
}

function fifoSimulation() {
    clearMemoryTable(); // 清空memory_table内容
    let pages = Array.from({ length: 32 }, (_, i) => new Page(i));//32页
    let memory = new Memory(4);
    memory.setMethod('FIFO')
    let instructions = generateInstructionSequence();
    let missingPages = 0;
    var count = 0;
    var index = 0;
    for (let i of instructions) {
        count++;
        let pageId = Math.floor(i / 10);
        if (!memory.hasInstruction(i)) {
            //需要判断是否已经装满
            let removedPage = memory.frames.length >= memory.size ? memory.frames[index].id : null;
            memory.frames[index] = pages[pageId];
            memory.lastUsedTime[index]=count;
            missingPages++;
            addInstructionToTable(count, i, memory, "是", index, removedPage);
            index = (index + 1) % 4;
        } else {
            addInstructionToTable(count, i, memory, "否", null, null);
        }
    }
    return missingPages / 320;
}

function lruSimulation() {
    clearMemoryTable(); // 清空memory_table内容

    let pages = Array.from({ length: 32 }, (_, i) => new Page(i));
    let memory = new Memory(4);
    memory.setMethod('LRU')
    let instructions = generateInstructionSequence();
    let missingPages = 0;
    var count = 0;
    var index = 0;
    for (let i of instructions) {
        count++;
        let pageId = Math.floor(i / 10);
        if (!memory.hasInstruction(i, count)) {
            index = memory.frames.findIndex(page => page === undefined);
            if (index === -1) {
                // 找到最早被访问的
                index = memory.lastUsedTime.indexOf(Math.min(...memory.lastUsedTime));
            }
            let removedPage = memory.frames[index] === undefined ? null : memory.frames[index].id;
            memory.frames[index] = pages[pageId];
            memory.lastUsedTime[index]=count;
            missingPages++;
            addInstructionToTable(count, i, memory, "是", index, removedPage);
        } else {
            addInstructionToTable(count, i, memory, "否", null, null);
        }
    }
    
    return missingPages / 320;
}

// 在文档准备好后执行的操作需要被封装在一个函数中
$(document).ready(function () {
    $("#fifo-button").click(function () {
        let missRate = fifoSimulation();
        $("#fifo_miss_page_times").text(missRate * 320);
        $("#fifo_miss_page_rate").text(missRate.toFixed(2));
        $(this).text("Restart");
    });

    $("#lru-button").click(function () {
        let missRate = lruSimulation();
        $("#lru_miss_page_times").text(missRate * 320);
        $("#lru_miss_page_rate").text(missRate.toFixed(2));
        $(this).text("Restart");
    });
});
while (sequence.length < 320) {
    console.log(sequence.length)
    // 如果存在编号为m+1的指令，则加入序列中
    if (m + 1 < 320 && !usedInstructions.has(m + 1)) {
        sequence.push(m + 1);
        usedInstructions.add(m + 1);
    }

    // 如果m大于0，即存在可以跳转的前地址部分的指令
    if (m > 0) {
        // 在0到m-1之间随机选择一个指令
        let m1 = Math.floor(Math.random() * m);
        while (usedInstructions.has(m1)) {
            m1 = Math.floor(Math.random() * m);
        }
        // 加入到序列中
        sequence.push(m1);
        usedInstructions.add(m1);

        // 如果存在编号为m1+1的指令，则加入序列中
        if (m1 + 1 < m && !usedInstructions.has(m1 + 1)) {
            sequence.push(m1 + 1);
            usedInstructions.add(m1 + 1);
        }

        m = m1;
    }

    // 如果存在可以跳转的后地址部分的指令
    if (m + 2 < 320) {
        // 在m+2到319之间随机选择一个指令
        let m2 = m + 2 + Math.floor(Math.random() * (319 - m - 1));
        while (usedInstructions.has(m2)) {
            m2 = m + 2 + Math.floor(Math.random() * (319 - m - 1));
        }
        // 加入到序列中
        sequence.push(m2);
        usedInstructions.add(m2);

        // 如果存在编号为m2+1的指令，则加入序列中
        if (m2 + 1 < 320 && !usedInstructions.has(m2 + 1)) {
            sequence.push(m2 + 1);
            usedInstructions.add(m2 + 1);
        }

        m = m2;
    }
}
while (sequence.length < 320) {
    console.log(sequence.length)
    // 如果存在编号为m+1的指令，则加入序列中
    if (m + 1 < 320 && !usedInstructions.has(m + 1)) {
        sequence.push(m + 1);
        usedInstructions.add(m + 1);
    }

    // 如果m大于0，即存在可以跳转的前地址部分的指令
    if (m > 0) {
        // 在0到m-1之间随机选择一个指令
        let m1 = Math.floor(Math.random() * m);
        while (usedInstructions.has(m1)) {
            m1 = Math.floor(Math.random() * m);
        }
        // 加入到序列中
        sequence.push(m1);
        usedInstructions.add(m1);

        // 如果存在编号为m1+1的指令，则加入序列中
        if (m1 + 1 < m && !usedInstructions.has(m1 + 1)) {
            sequence.push(m1 + 1);
            usedInstructions.add(m1 + 1);
        }

        m = m1;
    }

    // 如果存在可以跳转的后地址部分的指令
    if (m + 2 < 320) {
        // 在m+2到319之间随机选择一个指令
        let m2 = m + 2 + Math.floor(Math.random() * (319 - m - 1));
        while (usedInstructions.has(m2)) {
            m2 = m + 2 + Math.floor(Math.random() * (319 - m - 1));
        }
        // 加入到序列中
        sequence.push(m2);
        usedInstructions.add(m2);

        // 如果存在编号为m2+1的指令，则加入序列中
        if (m2 + 1 < 320 && !usedInstructions.has(m2 + 1)) {
            sequence.push(m2 + 1);
            usedInstructions.add(m2 + 1);
        }

        m = m2;
    }
}
