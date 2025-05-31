import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from python_utils.time import epoch

from torch.utils.data import DataLoader,Dataset

# 启用异常检测
torch.autograd.set_detect_anomaly(True)

class mydataset(Dataset):
    def __init__(self, input, target):
        self.input = input
        self.target = target

    def __len__(self):
        return len(self.input)

    def __getitem__(self, idx):
        return self.input[idx], self.target[idx]


def select_device():
    # 检查CUDA是否可用
    if torch.cuda.is_available():
        return torch.device('cuda')
    # 检查MPS（用于Mac M1/M2芯片）是否可用
    elif torch.backends.mps.is_available():
        return torch.device('mps')
    else:
    # 默认回退到CPU
        return torch.device('cpu')


# 按论文原文定义循环神经网络模型
class RNN(nn.Module):
    def __init__(self, input_size, hidden_size, output_size, dropout):
        super(RNN, self).__init__()
        # 确定超参数的值
        self.device = select_device()

        self.hidden_size = hidden_size
        self.x_layer = nn.Linear(input_size + hidden_size, hidden_size)
        self.h_layer = nn.Linear(hidden_size, hidden_size)
        self.relu = nn.ReLU()
        self.output_layer = nn.Linear(hidden_size, output_size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, X, Ht1):
        # 合并当前输入和前一个隐藏状态
        combined = torch.cat((X, Ht1), dim=1)
        temp = self.x_layer(combined)
        Ht = self.relu(temp)
        temp2 = self.dropout(Ht)
        output = self.output_layer(temp2)
        return Ht.cpu().detach().numpy(), output


def train(model: RNN, input, target, Ht1, lr=0.0001):
    model = model.to(select_device())
    model.train()
    #确保数据符合规范
    input_norm = torch.Tensor(input).to(torch.float32)
    target_norm = torch.Tensor(target).to(torch.float32)
    Ht1 = torch.Tensor(Ht1).to(torch.float32)
    Ht1 = Ht1.to(model.device)

    data = mydataset(input_norm, target_norm)

    #按照论文用来训练
    dataloader = DataLoader(dataset=data, batch_size=1, shuffle=True)
    optimizer = optim.Adam(model.parameters(), lr=lr)

    #训练epoch设置为50
    epoch_num = 5
    H_temp = None
    L = []
    for epoch in range(epoch_num):
        for idx, batch in enumerate(dataloader):
            train_input, train_target = batch
            train_input = train_input.to(model.device)
            train_target = train_target.to(model.device)

            optimizer.zero_grad()

            H_temp, pred = model(train_input, Ht1)
            loss = criterion(pred, train_target) * 0.5

            # 保存loss,后续辅助策略使用
            if epoch == epoch_num - 1:
                L.append(loss.item())

            loss.backward(retain_graph=True)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
    return H_temp, np.mean(L)

criterion = nn.MSELoss()


def predict_by_rnn(model: RNN, input, Ht1):
    model.eval()
    model.to(select_device())

    input = torch.Tensor(input)
    input = input.to(select_device())
    Ht1 = torch.Tensor(Ht1)
    Ht1 = Ht1.to(select_device())

    # 初始化一个列表来存储预测结果
    outputs = []

    # 逐个处理输入数据中的每个个体
    for i in range(input.size(0)):
        # 获取当前个体的输入
        current_input = input[i].unsqueeze(0)  # 增加一个批次维度，形状变为 [1, 10]

        # 使用 RNN 进行预测
        _, output = model(current_input, Ht1)

        # 将预测结果从张量转换为 NumPy 数组并存储
        outputs.append(output.cpu().detach().numpy())

    # 将所有预测结果合并为一个 NumPy 数组
    outputs = np.vstack(outputs)

    return outputs

