# SMILES 修正模型参数记录与最优配置

> 项目：`RetrosynthesisClaw` / `smiles` 子项目  
> 模型：`ChemBERTa-2` + 去噪修复头  
> 任务：将噪声 SMILES 修正为 canonical SMILES  
> 记录版本：当前训练方案（3 轮迭代修复、监督训练）

---

## 1. 目标与实现方法

本项目的 SMILES 修正模型目标是：

- 输入：人为制造噪声后的 SMILES
- 输出：RDKit 规范化后的 canonical SMILES
- 约束：如果模型第一次修复后仍然无效，则将修复结果再次输入，最多迭代 3 次

### 1.1 实现方法概述

整个流程拆分为两个独立脚本：

1. **数据处理脚本**：`smiles/prepare_smiles_data.py`
   - 读取 `smiles/data/raw/USPTO500MT_train.csv`
   - 提取 `reactants` 和 `products`
   - 对合法 SMILES 使用 RDKit 进行 canonicalization
   - 人为注入噪声，构造修复训练样本
   - 输出训练集与验证集 CSV

2. **训练脚本**：`smiles/train_smiles_repair.py`
   - 加载 `smiles/ChemBERTa-2`
   - 使用 ChemBERTa-2 作为编码器
   - 叠加轻量 Transformer 解码器
   - 训练噪声 SMILES -> canonical SMILES 的去噪生成模型
   - 输出训练日志、loss 曲线、配置与指标文件

### 1.2 修复策略

修复模型在 Agent 框架中的使用规则如下：

- 对输入 SMILES 做最多 3 次迭代修复
- 每次将上一轮修复结果再次作为输入
- 每一轮都进行 RDKit 校验
- 失败时保留原始值与修复轨迹，便于审计和统计

---

## 2. 数据处理参数记录

下面记录数据处理阶段的关键参数及其作用。

| 参数名称 | 数据类型 | 默认值 | 取值范围 | 作用与价值 |
|---|---:|---:|---:|---|
| `--input` | `Path` | `smiles/data/raw/USPTO500MT_train.csv` | 任意有效 CSV 路径 | 原始数据源路径，决定训练样本的母体规模与分布。 |
| `--output-dir` | `Path` | `smiles/data/processed` | 任意目录 | 输出处理后数据与数据摘要，便于复现实验。 |
| `--val-ratio` | `float` | `0.02` | `(0, 1)` | 验证集比例。过小会导致评估不稳定，过大则减少训练数据。 |
| `--seed` | `int` | `42` | 任意整数 | 随机种子，决定噪声注入与训练/验证切分的可复现性。 |
| `--max-rows` | `int` | `0` | `0` 或正整数 | 调试用行数上限。`0` 表示不截断。 |

### 2.1 数据处理阶段的关键价值

- **`reactants` 支持 `smiles.smiles` 形式**：
  - 通过 `.` 拆分为多个组分
  - 每个组分单独 canonicalize
  - 再排序拼接，保证混合物输入的稳定性
- **噪声注入策略**：
  - 删除、插入、替换、交换、外部引号包裹、额外点号等
  - 能覆盖常见模型输出错误
  - 为修复模型提供足够的“坏样本”分布

### 2.2 数据处理阶段的关键发现

1. `reactants` 往往比 `products` 更复杂，包含多组分与分隔符 `.`。
2. 直接把模型输出作为目标训练会导致模型偏向记忆，而不是纠错，因此必须构造噪声输入。
3. canonicalization 是必要步骤，否则同一分子可能出现多个等价写法，影响监督学习稳定性。

---

## 3. 训练参数记录

下面记录当前 SMILES 修正模型的训练参数。

| 参数名称 | 数据类型 | 默认值 | 取值范围 | 作用与价值 |
|---|---:|---:|---:|---|
| `--model-dir` | `Path` | `smiles/ChemBERTa-2` | 任意本地模型目录 | 预训练编码器来源。决定化学语义表征质量。 |
| `--train-file` | `Path` | `smiles/data/processed/smiles_repair_train.csv` | 任意训练集 CSV | 训练样本来源。 |
| `--val-file` | `Path` | `smiles/data/processed/smiles_repair_val.csv` | 任意验证集 CSV | 验证样本来源。 |
| `--output-dir` | `Path` | `smiles/runs/chemberta2_repair` | 任意目录 | 输出模型、日志与图表。 |
| `--max-input-length` | `int` | `192` | 正整数 | 输入端最大 token 长度。过短会截断复杂分子，过长会增加显存与训练时间。 |
| `--max-target-length` | `int` | `192` | 正整数 | 输出端最大 token 长度。用于控制生成目标长度与训练稳定性。 |
| `--batch-size` | `int` | `16` | 正整数 | 每步批大小。越大越稳定，但更耗显存。 |
| `--grad-accumulation` | `int` | `1` | 正整数 | 梯度累积步数。可在显存不足时模拟更大批量。 |
| `--learning-rate` | `float` | `5e-5` | `>0` | 学习率。过高易震荡，过低收敛慢。 |
| `--weight-decay` | `float` | `0.01` | `>=0` | 权重衰减，抑制过拟合。 |
| `--epochs` | `int` | `3` | 正整数 | 训练轮数。决定拟合程度与过拟合风险。 |
| `--warmup-ratio` | `float` | `0.03` | `[0, 1)` | warmup 比例，帮助前期稳定训练。 |
| `--max-train-samples` | `int` | `0` | `0` 或正整数 | 训练集子采样，用于快速试验。 |
| `--max-val-samples` | `int` | `0` | `0` 或正整数 | 验证集子采样，用于快速试验。 |
| `--seed` | `int` | `42` | 任意整数 | 控制训练可复现性。 |
| `--fp16` | `bool` | `False` | `True/False` | 混合精度训练，提速省显存。 |
| `--num-workers` | `int` | `0` | `>=0` | DataLoader 并行数。 |
| `--decoder-layers` | `int` | `2` | 正整数 | 解码器层数。层数越多表达能力越强，但训练更慢。 |
| `--decoder-heads` | `int` | `8` | 正整数且可整除 hidden size | 多头注意力头数。影响生成能力与并行表达。 |

---

## 4. 当前最优配置

以下是当前实验中采用并表现较优的配置。

### 4.1 数据与噪声配置

| 项 | 最优值 | 说明 |
|---|---:|---|
| 原始数据集 | `USPTO500MT_train.csv` | 覆盖大规模反应对，适合生成修复噪声对。 |
| 训练样本数 | `153274` | 当前处理后训练集规模。 |
| 验证样本数 | `3128` | 当前验证集规模。 |
| 验证比例 | `0.02` | 在当前任务中兼顾稳定评估与足够训练样本。 |
| 噪声策略 | 字符级 corruption + 轻文本噪声 | 对真实错误模式有较好覆盖。 |
| 最大修复轮数 | `3` | 兼顾效果与推理成本。 |

### 4.2 模型训练配置

| 项 | 最优值 | 说明 |
|---|---:|---|
| Backbone | `ChemBERTa-2` | 保留化学语义先验。 |
| 编码长度 | `192` | 对大多数分子足够，且显存占用可控。 |
| 批大小 | `16` | 在当前环境下较稳。 |
| 梯度累积 | `1` | 当前训练规模下不需要额外累积。 |
| 学习率 | `5e-5` | 收敛与稳定性平衡较好。 |
| 权重衰减 | `0.01` | 能有效抑制过拟合。 |
| Epoch | `3` | 当前任务上已观察到明显收敛，继续增加收益有限。 |
| Warmup ratio | `0.03` | 起步稳定，避免前期震荡。 |
| 解码器层数 | `2` | 表达能力与速度的平衡点。 |
| 解码器头数 | `8` | 与 hidden size 兼容，训练表现稳定。 |
| FP16 | `False` | 当前为稳定优先配置。 |

---

## 5. 训练结果与性能价值分析

### 5.1 当前训练结果

当前运行得到的关键指标如下：

| 指标 | 数值 | 解释 |
|---|---:|---|
| `train_loss` | `0.5828` | 训练损失已收敛到较低水平。 |
| `eval_loss` | `0.2699` | 验证损失进一步降低，说明模型泛化较好。 |
| `train_runtime` | `1683.61s` | 当前训练耗时。 |
| `best_model_checkpoint` | `checkpoint-28000` | 最优验证点出现较早，说明模型在中后段已达到较佳状态。 |

### 5.2 参数对性能的具体影响

#### 学习率 `5e-5`
- 优点：收敛速度与稳定性平衡较好。
- 价值：适合从预训练 ChemBERTa backbone 上进行下游微调。
- 风险：如果继续增大学习率，可能损伤预训练表示。

#### 训练轮数 `3`
- 优点：当前已足够让模型对噪声模式形成稳定映射。
- 价值：在大数据场景中，3 个 epoch 通常已能达到较高收益。
- 风险：继续增加可能带来过拟合或收益递减。

#### 最大输入/输出长度 `192`
- 优点：在显存和覆盖率之间取得折中。
- 价值：适合多数 USPTO 分子长度，减少无效截断。
- 风险：对于极长分子可能仍需更大长度。

#### 解码器层数 `2`
- 优点：轻量、易训、收敛快。
- 价值：适合先验证 SMILES 去噪任务的可行性。
- 风险：对于复杂重构任务，表达能力可能不足。

#### 批大小 `16`
- 优点：训练稳定，梯度噪声适中。
- 价值：当前环境下较平衡，适用于单卡/中等显存。
- 风险：显存更充足时可尝试更大 batch 提升吞吐。

#### 权重衰减 `0.01`
- 优点：降低过拟合风险。
- 价值：对大规模化学文本任务通常有效。
- 风险：过强则可能限制收敛。

#### 最大修复轮数 `3`
- 优点：能显著提高“二次修复”后的成功率。
- 价值：适合工程化部署，避免无限循环。
- 风险：过多轮数会增加延迟，且可能引入漂移。

---

## 6. 调参过程中的关键发现

### 6.1 数据层面的发现

1. **直接用原始 SMILES 训练修复效果不稳定**。
   - 必须先制造噪声，否则模型学到的只是记忆映射。

2. **Reactants 的多组分形式是重要难点**。
   - `smiles.smiles` 形式需要拆分后分别处理。
   - 否则模型会把 `.` 结构与分子边界混淆。

3. **canonicalization 很关键**。
   - 同一分子多种表示会增加监督信号噪声。
   - 统一到 canonical SMILES 后，训练更稳定。

### 6.2 模型层面的发现

1. **ChemBERTa-2 作为编码器是有价值的**。
   - 能保留化学语义先验。
   - 对 SMILES 修复比从零训练更高效。

2. **轻量 decoder 足以完成第一阶段修复任务**。
   - 不需要一开始就上很重的生成模型。
   - 先验证任务可行性更重要。

3. **验证损失低于训练损失是合理的**。
   - 说明验证集相对更规整或噪声分布更集中。
   - 也可能说明训练集噪声更丰富，任务更难。

### 6.3 工程层面的发现

1. **训练与数据处理分离非常必要**。
   - 便于重复实验与调参。

2. **日志与曲线必须保留**。
   - 否则无法比较不同噪声策略与超参数。

3. **修复过程必须保留 metadata**。
   - 用于分析失败模式和后续改进。

---

## 7. 最终推荐的最优参数配置

下面给出当前建议作为默认方案使用的配置。

```json
{
  "model_dir": "smiles/ChemBERTa-2",
  "train_file": "smiles/data/processed/smiles_repair_train.csv",
  "val_file": "smiles/data/processed/smiles_repair_val.csv",
  "output_dir": "smiles/runs/chemberta2_repair",
  "max_input_length": 192,
  "max_target_length": 192,
  "batch_size": 16,
  "grad_accumulation": 1,
  "learning_rate": 5e-05,
  "weight_decay": 0.01,
  "epochs": 3,
  "warmup_ratio": 0.03,
  "seed": 42,
  "fp16": false,
  "decoder_layers": 2,
  "decoder_heads": 8,
  "max_repair_rounds": 3
}
```

---

## 8. 实际部署建议

### 8.1 在线推理

在 Agent 中，推荐如下顺序：

1. 原始 SMILES 输入
2. 调用修复模型
3. 如果无效，继续将修复后的 SMILES 再输入一次
4. 最多重复 3 轮
5. 若仍无效，则保留原始输入并打标失败

### 8.2 监控指标

上线后建议持续记录：

- 初次修复成功率
- 三轮内修复成功率
- 过修复率（原本有效却被改坏）
- canonical match rate
- 每类噪声错误的修复成功率

### 8.3 后续可进一步优化的方向

- 增加 beam search 推理
- 统计真实错误分布后再进行定向噪声注入
- 加入更多立体化学相关噪声样本
- 将修复结果与 RDKit 校验联动做二次筛查

---

## 9. 文件与产物清单

本次实验相关产物包括：

- `smiles/prepare_smiles_data.py`
- `smiles/train_smiles_repair.py`
- `smiles/runs/chemberta2_repair/final_model/`
- `smiles/runs/chemberta2_repair/loss_curve.png`
- `smiles/runs/chemberta2_repair/metrics.json`
- `smiles/runs/chemberta2_repair/trainer_log_history.jsonl`
- `smiles/runs/chemberta2_repair/run_summary.json`

---

## 10. 结论

当前 SMILES 修正模型已经形成了可落地的工程闭环：

- 数据准备独立
- 训练过程独立
- 参数可追踪
- 曲线可视化可保存
- Agent 内可执行最多 3 轮迭代修复

就当前实验结果来看，`learning_rate=5e-5`、`batch_size=16`、`epochs=3`、`decoder_layers=2`、`decoder_heads=8` 是一组较稳健的默认配置，适合作为后续迭代优化的基线。
