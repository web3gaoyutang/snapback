# 使用示例

## 示例1: 分析浦发银行 (600000)

### 输入参数
- 股票代码: `600000` 或 `sh.600000`
- 总投资金额: `100,000` 元

### 预期输出

系统会分析浦发银行最近60天的涨停记录，假设找到涨停信息：

```
涨停日期: 2025-10-15
涨停价格: ¥12.50
最高价格: ¥13.80
最低价格: ¥11.20
当前价格: ¥12.00
```

### 斐波那契回调位计算

高低价差: 13.80 - 11.20 = 2.60

| 回调位 | 价格计算 | 价格 |
|--------|----------|------|
| 0.382 | 13.80 - 2.60 × 0.382 | ¥12.81 |
| 0.500 | 13.80 - 2.60 × 0.500 | ¥12.50 |
| 0.618 | 13.80 - 2.60 × 0.618 | ¥12.19 |
| 0.700 | 13.80 - 2.60 × 0.700 | ¥11.98 |
| 0.786 | 13.80 - 2.60 × 0.786 | ¥11.76 |

### 订单生成

**第一阶段 (0.5-0.618回调)** - 70,000元，分5笔

| 订单号 | 价格 | 金额 | 占比 | 股数 |
|--------|------|------|------|------|
| 1 | ¥12.50 | ¥14,000 | 14% | 1,100股 |
| 2 | ¥12.42 | ¥14,000 | 14% | 1,100股 |
| 3 | ¥12.34 | ¥14,000 | 14% | 1,100股 |
| 4 | ¥12.27 | ¥14,000 | 14% | 1,100股 |
| 5 | ¥12.19 | ¥14,000 | 14% | 1,100股 |

**第二阶段 (0.618-0.7回调)** - 30,000元，分3笔

| 订单号 | 价格 | 金额 | 占比 | 股数 |
|--------|------|------|------|------|
| 6 | ¥12.19 | ¥10,000 | 10% | 800股 |
| 7 | ¥12.09 | ¥10,000 | 10% | 800股 |
| 8 | ¥11.98 | ¥10,000 | 10% | 800股 |

### 策略解读

1. **第一阶段**: 在相对安全的0.5-0.618回调区间，投入70%的资金
2. **第二阶段**: 在更深的0.618-0.7回调区间，投入剩余30%的资金
3. **金字塔效应**: 越跌越买，但金额逐步减少，控制风险

---

## 示例2: 分析贵州茅台 (600519)

### 输入参数
- 股票代码: `600519`
- 总投资金额: `500,000` 元

### 特点
- 高价股，每手价格较高
- 同样按7:3比例分配
- 第一阶段: 350,000元，每单70,000元
- 第二阶段: 150,000元，每单50,000元

---

## 示例3: 分析创业板股票 (300750)

### 输入参数
- 股票代码: `300750` 或 `sz.300750`
- 总投资金额: `200,000` 元

### 注意事项
- 创业板涨跌幅限制为20%
- 系统仍按9.5%阈值查找涨停（可配置）
- 波动较大，风险较高

---

## API调用示例

### 使用curl分析股票

```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "600000",
    "total_amount": 100000
  }'
```

### 使用Python调用

```python
import requests

# 分析股票
response = requests.post('http://localhost:5000/api/analyze', json={
    'stock_code': '600000',
    'total_amount': 100000
})

result = response.json()

if result['success']:
    data = result['data']
    print(f"股票代码: {data['stock_code']}")
    print(f"订单数量: {data['summary']['total_orders']}")

    for order in data['orders']:
        print(f"订单{order['order_no']}: ¥{order['price']} × {order['amount']}")
else:
    print(f"错误: {result['message']}")
```

### 使用JavaScript调用

```javascript
// 分析股票
async function analyzeStock(stockCode, totalAmount) {
    const response = await fetch('http://localhost:5000/api/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            stock_code: stockCode,
            total_amount: totalAmount
        })
    });

    const result = await response.json();

    if (result.success) {
        console.log('分析成功:', result.data);
        return result.data;
    } else {
        console.error('分析失败:', result.message);
        return null;
    }
}

// 调用
analyzeStock('600000', 100000);
```

---

## 执行订单示例

### 模拟模式（默认）

```bash
curl -X POST http://localhost:5000/api/execute \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "sh.600000",
    "orders": [
      {"price": 12.50, "amount": 14000},
      {"price": 12.42, "amount": 14000}
    ],
    "account_id": "",
    "account_key": ""
  }'
```

响应：
```json
{
  "success": true,
  "data": {
    "total": 2,
    "success": 2,
    "failed": 0,
    "results": [
      {
        "order": {"price": 12.50, "amount": 14000},
        "success": true,
        "order_id": "MOCK_sh.600000_12.50_1100",
        "volume": 1100,
        "message": "模拟订单已提交"
      }
    ]
  }
}
```

---

## 查询历史订单

### 获取最近10条订单

```bash
curl http://localhost:5000/api/history?limit=10
```

### 获取特定股票的订单

```bash
curl http://localhost:5000/api/history?stock_code=sh.600000
```

### 获取统计信息

```bash
curl http://localhost:5000/api/statistics
```

响应：
```json
{
  "success": true,
  "data": {
    "total_orders": 25,
    "total_stocks": 5,
    "total_amount": 1250000,
    "first_order_date": "2025-11-01T10:30:00",
    "last_order_date": "2025-11-04T15:45:00"
  }
}
```

---

## 常见问题

### Q1: 为什么没有找到涨停记录？

**A**: 可能的原因：
1. 该股票最近60天内没有涨停
2. 数据源问题，建议重试
3. 股票代码输入错误

**解决方案**:
- 选择近期有过涨停的股票
- 检查股票代码是否正确
- 增加查找天数（需修改配置）

### Q2: 为什么计算出的股数是0？

**A**: 金额不足一手（100股）

**解决方案**:
- 增加总投资金额
- 选择价格较低的股票

### Q3: 如何修改仓位分配比例？

**A**: 编辑 `backend/config.py`:

```python
PYRAMID_CONFIG = {
    'stage1': {
        'fib_start': 0.500,
        'fib_end': 0.618,
        'position_ratio': 0.80,  # 改为80%
        'order_count': 4,         # 改为4笔
    },
    'stage2': {
        'fib_start': 0.618,
        'fib_end': 0.700,
        'position_ratio': 0.20,  # 改为20%
        'order_count': 2,         # 改为2笔
    }
}
```

### Q4: 如何启用真实交易？

**A**:
1. 编辑 `backend/config.py`:
```python
MOCK_MODE = False
XT_ACCOUNT_ID = '你的账户ID'
XT_ACCOUNT_KEY = '你的账户密钥'
```

2. 安装并配置 XTTrader 客户端

3. 修改 `backend/xt_trader.py` 中的实际交易逻辑

⚠️ **警告**: 真实交易前请充分测试！

---

## 风险提示

⚠️ **本系统仅供学习研究使用**

1. **不保证盈利**: 历史回调不代表未来一定会回调
2. **可能损失**: 市场可能跌破所有回调位
3. **流动性风险**: 某些价位可能无法成交
4. **时机风险**: 涨停后可能持续上涨不回调

**建议**:
- 先用小额资金测试
- 结合基本面分析
- 设置止损止盈
- 不要孤注一掷
