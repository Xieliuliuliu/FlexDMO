import torch
import torch.nn as nn
from torch.utils.data import DataLoader,Dataset
import torch.optim as optim

E_min = 0.005
T_max = 10
learning_rate = 0.1

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

criterion = nn.MSELoss().to(select_device())

# 自定义神经网络
class ANN(nn.Module):
    def __init__(self, dim, hidden):
        super(ANN, self).__init__()

        # 确定超参数的值
        self.device = select_device()

        self.layers = nn.Sequential(
            nn.Linear(dim, hidden),
            nn.Sigmoid(),
            nn.Linear(hidden, dim),
            nn.Sigmoid(),
        )
    def forward(self, x):
        return self.layers(x)

def data_normalize(data, x_low, x_upp):
    """将张量按论文的方式标准化"""
    return (data - x_low) / (x_upp - x_low)

def inverse_data(data, x_low, x_upp):
    """将结果数据还原"""
    return data * (x_upp - x_low) + x_low


def train(model: ANN, input, target, X_Low, X_Upp):
    model = model.to(model.device)

    input_norm = data_normalize(input, X_Low, X_Upp)
    target_norm = data_normalize(target, X_Low, X_Upp)
    #确保数据符合规范
    input_norm = torch.Tensor(input_norm).to(torch.float32)
    target_norm = torch.Tensor(target_norm).to(torch.float32)
    data = mydataset(input_norm, target_norm)

    dataloader = DataLoader(dataset=data, batch_size=1, shuffle=True)
    optimizer = optim.SGD(model.parameters(),lr=learning_rate,momentum=0.8)

    T = 0
    #E初始比设定的终止条件大就行
    E = 1
    while E > E_min and T < T_max:
        epoch_loss = 0
        for idx, batch in enumerate(dataloader):
            train_input, train_target = batch
            train_input = train_input.to(model.device)
            train_target = train_target.to(model.device)
            pred = model(train_input)
            loss = criterion(pred, train_target)
            epoch_loss += loss.item()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        E = epoch_loss / len(dataloader)
        T = T + 1

def predict_by_ann(model: ANN, input, X_Low, X_Upp):
    input_norm = torch.Tensor(data_normalize(input, X_Low, X_Upp)).to(model.device)
    logits = model(input_norm)
    result = inverse_data(logits.detach().cpu(), X_Low, X_Upp)
    result = result.numpy()
    return result

class mydataset(Dataset):
    def __init__(self, input, target):
        self.input = input
        self.target = target
    def __len__(self):
        return len(self.input)
    def __getitem__(self, idx):
        return self.input[idx], self.target[idx]