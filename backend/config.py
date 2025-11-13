# 配置文件

## 服务配置
HOST = '0.0.0.0'
PORT = 5000
DEBUG = True

## 策略配置
# 查找涨停的时间范围（天）
LIMIT_UP_SEARCH_DAYS = 60

# 涨停阈值（百分比）
LIMIT_UP_THRESHOLD = 9.5

# 金字塔建仓配置
PYRAMID_CONFIG = {
    # 第一阶段：0.5-0.618回调
    'stage1': {
        'fib_start': 0.500,
        'fib_end': 0.618,
        'position_ratio': 0.70,  # 70%仓位
        'order_count': 5,
    },
    # 第二阶段：0.618-0.7回调
    'stage2': {
        'fib_start': 0.618,
        'fib_end': 0.700,
        'position_ratio': 0.30,  # 30%仓位
        'order_count': 3,
    }
}

## XTTrader配置
# 是否使用模拟模式（True=模拟，False=真实交易）
MOCK_MODE = True

# XTTrader账户配置（真实交易时填写）
XT_ACCOUNT_ID = ''
XT_ACCOUNT_PATH = ''
XT_SESSION_ID = ''

## 日志配置
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
