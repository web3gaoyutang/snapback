"""
Flask API服务
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from typing import Dict, Any, Optional, Tuple
import logging
import os
from functools import wraps

from strategy import FibonacciPyramidStrategy
from xt_trader import XTTraderClient
from storage import OrderStorage
from utils import validate_stock_code
import config

# 配置日志
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='../frontend', static_url_path='')
CORS(app)

# 初始化策略、交易客户端和存储
strategy = FibonacciPyramidStrategy()
trader: Optional[XTTraderClient] = None
storage = OrderStorage()


# 辅助函数
def success_response(data: Any = None, message: str = '') -> Tuple[Dict[str, Any], int]:
    """
    构建成功响应

    Args:
        data: 响应数据
        message: 响应消息

    Returns:
        (响应字典, HTTP状态码)
    """
    response = {'success': True}
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return jsonify(response), 200


def error_response(message: str, status_code: int = 400) -> Tuple[Dict[str, Any], int]:
    """
    构建错误响应

    Args:
        message: 错误消息
        status_code: HTTP状态码

    Returns:
        (响应字典, HTTP状态码)
    """
    return jsonify({
        'success': False,
        'message': message
    }), status_code


def handle_exceptions(func):
    """
    异常处理装饰器

    Args:
        func: 被装饰的函数

    Returns:
        装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValueError as e:
            logger.warning(f"{func.__name__}: 参数错误 - {e}")
            return error_response(str(e), 400)
        except Exception as e:
            logger.error(f"{func.__name__}: 处理失败 - {e}", exc_info=True)
            return error_response(str(e), 500)
    return wrapper


def ensure_trader_connected() -> Tuple[bool, Optional[str]]:
    """
    确保交易客户端已连接

    Returns:
        (是否成功, 错误消息)
    """
    global trader
    
    if trader is None or not trader.is_connected:
        try:
            trader = XTTraderClient(config.XT_ACCOUNT_PATH, config.XT_ACCOUNT_ID)
            if not trader.connect():
                return False, 'XTTrader连接失败'
        except Exception as e:
            logger.error(f"初始化交易客户端失败: {e}", exc_info=True)
            return False, f'初始化交易客户端失败: {str(e)}'
    
    return True, None


@app.route('/')
def index():
    """首页"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/analyze', methods=['POST'])
@handle_exceptions
def analyze_stock():
    """
    分析股票并生成订单计划

    请求体:
    {
        "stock_code": "sh.600000",
        "total_amount": 100000
    }
    """
    data = request.json or {}
    stock_code = data.get('stock_code', '').strip()
    total_amount = data.get('total_amount', 0)

    # 参数验证
    if not stock_code:
        return error_response('请输入股票代码', 400)

    try:
        total_amount = float(total_amount)
    except (ValueError, TypeError):
        return error_response('请输入有效的总金额', 400)

    if total_amount <= 0:
        return error_response('总金额必须大于0', 400)

    # 验证并标准化股票代码格式
    valid, result = validate_stock_code(stock_code)
    if not valid:
        return error_response(result, 400)

    stock_code = result
    logger.info(f"分析股票: {stock_code}, 总金额: {total_amount}")

    try:
        # 生成订单计划
        result = strategy.generate_pyramid_orders(stock_code, total_amount)

        # 保存订单记录
        order_id = storage.save_order(result)
        result['order_id'] = order_id

        logger.info(f"订单已保存，ID: {order_id}")

        return success_response(result)

    finally:
        # 确保登出baostock
        try:
            strategy.logout_baostock()
        except Exception as e:
            logger.warning(f"登出baostock失败: {e}")


@app.route('/api/execute', methods=['POST'])
@handle_exceptions
def execute_orders():
    """
    执行订单

    请求体:
    {
        "stock_code": "sh.600000",
        "orders": [
            {"price": 10.5, "amount": 14000},
            ...
        ]
    }
    """
    data = request.json or {}
    stock_code = data.get('stock_code', '').strip()
    orders = data.get('orders', [])

    # 参数验证
    if not stock_code:
        return error_response('缺少股票代码', 400)

    if not orders or not isinstance(orders, list):
        return error_response('缺少订单列表或订单列表格式错误', 400)

    logger.info(f"执行订单: {stock_code}, 订单数量: {len(orders)}")

    # 确保交易客户端已连接
    connected, error_msg = ensure_trader_connected()
    if not connected:
        return error_response(error_msg, 500)

    # 准备订单列表
    order_list = []
    for idx, order in enumerate(orders, 1):
        if not isinstance(order, dict):
            logger.warning(f"订单 {idx} 格式错误，已跳过")
            continue
        
        order_list.append({
            'stock_code': stock_code,
            'price': order.get('price'),
            'amount': order.get('amount')
        })

    if not order_list:
        return error_response('没有有效的订单', 400)

    # 批量下单
    results = trader.batch_place_orders(order_list)

    # 统计结果
    success_count = sum(1 for r in results if r['success'])
    fail_count = len(results) - success_count

    return success_response({
        'total': len(results),
        'success': success_count,
        'failed': fail_count,
        'results': results
    })


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return success_response({
        'status': 'ok',
        'service': 'Fibonacci Pyramid Trading System'
    })


@app.route('/api/history', methods=['GET'])
@handle_exceptions
def get_order_history():
    """
    获取订单历史记录

    查询参数:
    - limit: 返回数量（默认10）
    - stock_code: 筛选特定股票
    """
    try:
        limit = int(request.args.get('limit', 10))
    except (ValueError, TypeError):
        limit = 10

    if limit < 1 or limit > 100:
        limit = 10

    stock_code = request.args.get('stock_code', '').strip()

    # 获取订单
    if stock_code:
        orders = storage.get_orders_by_stock(stock_code)
    else:
        orders = storage.get_recent_orders(limit)

    return success_response({
        'orders': orders,
        'count': len(orders)
    })


@app.route('/api/statistics', methods=['GET'])
@handle_exceptions
def get_statistics():
    """获取统计信息"""
    stats = storage.get_statistics()
    return success_response(stats)


@app.route('/api/order/<order_id>', methods=['GET'])
@handle_exceptions
def get_order_detail(order_id: str):
    """
    获取订单详情

    路径参数:
    - order_id: 订单ID
    """
    order = storage.get_order_by_id(order_id)

    if order is None:
        return error_response('订单不存在', 404)

    return success_response(order)


@app.route('/api/order/<order_id>', methods=['DELETE'])
@handle_exceptions
def delete_order(order_id: str):
    """
    删除订单记录

    路径参数:
    - order_id: 订单ID
    """
    success = storage.delete_order(order_id)

    if not success:
        return error_response('订单不存在', 404)

    return success_response(message='订单已删除')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', config.PORT))
    app.run(host=config.HOST, port=port, debug=config.DEBUG)
