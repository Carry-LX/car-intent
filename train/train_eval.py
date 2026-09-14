"""
模型训练和评估模块

日志输出指标说明（以intent.log为例）：
  
  Precision: 0.8899 - 模型预测为某个意图的样本中，实际正确的比例
    意义：模型误报率低，预测的意图可信度高
  
  Recall: 0.8491 - 实际某个意图的样本中，被模型正确识别的比例
    意义：模型漏报率，有15%的真实意图被遗漏
  
  F1: 0.8452 - Precision和Recall的调和平均
    意义：综合评估，Precision(0.8899)和Recall(0.8491)的平衡指标
  
  Accuracy: 0.8573 - 所有样本中预测正确的比例
    意义：模型整体准确率，85.73%的样本预测正确
  
  Accuracy@3: 0.9632 - 真实意图在模型预测的top-3中的比例
    意义：即使第一选择错误，96.32%的样本真实意图在前3个预测中
  
  Accuracy@5: 0.9749 - 真实意图在模型预测的top-5中的比例
    意义：97.49%的样本真实意图在前5个预测中，模型基本能识别出正确意图
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn import metrics
import time
from data_helper import get_time_dif
from core.optimization import BertAdam
from utils import logger


def train(config, model, train_iter, dev_iter, test_iter):
    start_time = time.time()
    model.train()
    param_optimizer = list(model.named_parameters())
    no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']#在 BERT 类模型中，不应对偏置（bias）和 LayerNorm 参数施加 L2 正则化（weight decay），否则会影响模型稳定性。
    optimizer_grouped_parameters = [
        {'params': [p for n, p in param_optimizer if not any(nd in n for nd in no_decay)], 'weight_decay': 0.01},
        {'params': [p for n, p in param_optimizer if any(nd in n for nd in no_decay)], 'weight_decay': 0.0}]

    optimizer = BertAdam(optimizer_grouped_parameters,
                         lr=config.learning_rate,
                         warmup=0.05,#学习率预热
                         t_total=len(train_iter) * config.num_epochs)

    total_batch = 1  # 记录进行到多少batch
    dev_best_loss = float('inf')
    last_improve = 0  # 记录上次验证集loss下降的batch数
    flag = False  # 记录是否很久没有效果提升
    model.train()
    for epoch in range(config.num_epochs):
        logger.info('Epoch [{}/{}]'.format(epoch + 1, config.num_epochs))
        for i, (trains, labels) in enumerate(train_iter):
            outputs = model(trains)
            model.zero_grad()
            loss = F.cross_entropy(outputs, labels)
            loss.backward()
            optimizer.step()
            if total_batch  % 100 == 0:
                # 每多少轮输出在训练集和验证集上的效果
                true = labels.data.cpu()
                predic = torch.max(outputs.data, 1)[1].cpu() #从模型的原始输出（logits）中，找出每个样本预测概率最高的类别，并返回其类别索引（即预测标签）。
                train_acc = metrics.accuracy_score(true, predic)
                dev_acc, dev_loss = evaluate(config, model, dev_iter)
                if dev_loss < dev_best_loss:
                    dev_best_loss = dev_loss
                    torch.save(model.state_dict(), config.save_path)
                    improve = '*'
                    last_improve = total_batch
                else:
                    improve = ''
                time_dif = get_time_dif(start_time)
                msg = 'Iter: {0:>6},  Train Loss: {1:>5.2},  Train Acc: {2:>6.2%},  Val Loss: {3:>5.2},  Val Acc: {4:>6.2%},  Time: {5} {6}'
                logger.info(msg.format(total_batch, loss.item(), train_acc, dev_loss, dev_acc, time_dif, improve))
                model.train()
            total_batch += 1
            if total_batch - last_improve > config.require_improvement:
                # 早停止
                logger.info("No optimization for a long time, auto-stopping...")
                flag = True
                break
        if flag:
            break

    test(config, model, test_iter)


def test(config, model, test_iter):
    # test
    logger.info("="* 50)
    model.load_state_dict(torch.load(config.save_path))
    model.eval()
    start_time = time.time()
    result = evaluate(config, model, test_iter, test=True)

    logger.info(f"Precision: {result['precision']}")
    logger.info(f"Recall: {result['recall']}")
    logger.info(f"F1: {result['f1']}")
    logger.info(f"Accuracy: {result['acc']}")
    if config.dataset == "intent":
        logger.info(f"Accuracy@3: {result['acc@3']}")
        logger.info(f"Accuracy@5: {result['acc@5']}")
    time_dif = get_time_dif(start_time)
    logger.info(f"Time usage: {time_dif}")


def evaluate(config, model, data_iter, test=False):
    """
    计算模型性能指标
    
    核心计算：
    - Accuracy: 预测正确数 / 总数
    - Precision/Recall/F1: 对每个类别分别计算，然后宏平均
    - Accuracy@k: 检查真实标签是否在top-k预测中
    """
    model.eval()
    loss_total = 0
    predict_all = np.array([], dtype=int) #所有预测标签
    labels_all = np.array([], dtype=int)
    probs_all = [] #所有预测概率（用于 top-k 准确率）
    with torch.no_grad():
        for texts, labels in data_iter:
            outputs = model(texts)
            loss = F.cross_entropy(outputs, labels)
            loss_total += loss
            labels = labels.data.cpu().numpy()
            prob = F.softmax(outputs,dim=-1).cpu().numpy() #将输出转为概率softmax
            predic = torch.max(outputs.data, 1)[1].cpu().numpy() #获取预测类别
            labels_all = np.append(labels_all, labels)
            predict_all = np.append(predict_all, predic)
            probs_all.extend(prob.tolist())

    probs_all = np.array(probs_all)
    result = {}
    acc = metrics.accuracy_score(labels_all, predict_all)
    result["acc"] = acc
    if test:
        precision = metrics.precision_score(labels_all, predict_all, average="macro")
        recall = metrics.recall_score(labels_all, predict_all, average="macro")
        f1 = metrics.f1_score(labels_all, predict_all, average="macro")
        result["precision"] = precision
        result["recall"] = recall 
        result["f1"] = f1
        if config.dataset == "intent":
            for k in [3, 5]:
                acc_k = metrics.top_k_accuracy_score(labels_all, probs_all, k=k, normalize=True, labels=range(len(config.class_list)))
                result[f"acc@{k}"] = acc_k
        return result 
    return acc, loss_total / len(data_iter)
