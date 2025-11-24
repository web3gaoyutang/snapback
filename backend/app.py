"""
Flask API服务
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
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
trader = None
storage = OrderStorage()


@app.route('/')
def index():
    """首页"""
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/api/analyze', methods=['POST'])
def analyze_stock():
    """
    分析股票并生成订单计划

    请求体:
    {
        "stock_code": "sh.600000",
        "total_amount": 100000
    }
    """
    try:
        data = request.json
        stock_code = data.get('stock_code', '').strip()
        total_amount = float(data.get('total_amount', 0))

        if not stock_code:
            return jsonify({
                'success': False,
                'message': '请输入股票代码'
            }), 400

        if total_amount <= 0:
            return jsonify({
                'success': False,
                'message': '请输入有效的总金额'
            }), 400

        # 验证并标准化股票代码格式
        valid, result = validate_stock_code(stock_code)
        if not valid:
            return jsonify({
                'success': False,
                'message': result
            }), 400

        stock_code = result

        logger.info(f"分析股票: {stock_code}, 总金额: {total_amount}")

        # 生成订单计划
        result = strategy.generate_pyramid_orders(stock_code, total_amount)

        # 保存订单记录
        order_id = storage.save_order(result)
        result['order_id'] = order_id

        logger.info(f"订单已保存，ID: {order_id}")

        return jsonify({
            'success': True,
            'data': result
        })

    except Exception as e:
        logger.error(f"分析失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
    finally:
        # 确保登出baostock
        try:
            strategy.logout_baostock()
        except:
            pass


@app.route('/api/execute', methods=['POST'])
def execute_orders():
    """
    执行订单

    请求体:
    {
        "stock_code": "sh.600000",
        "orders": [
            {"price": 10.5, "amount": 14000},
            ...
        ],
        "account_id": "",
        "account_key": ""
    }
    """
    global trader

    try:
        data = request.json
        stock_code = data.get('stock_code', '').strip()
        orders = data.get('orders', [])
        # account_id = data.get('account_id', '').strip()
        # account_key = data.get('account_key', '').strip()

        if not stock_code or not orders:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400

        logger.info(f"执行订单: {stock_code}, 订单数量: {len(orders)}")

        # 初始化交易客户端
        if trader is None or not trader.is_connected:
            trader = XTTraderClient(config.XT_ACCOUNT_PATH, config.XT_ACCOUNT_ID)
            if not trader.connect():
                return jsonify({
                    'success': False,
                    'message': 'XTTrader连接失败'
                }), 500

        # 准备订单
        order_list = []
        for order in orders:
            order_list.append({
                'stock_code': stock_code,
                'price': order['price'],
                'amount': order['amount']
            })

        # 批量下单
        results = trader.batch_place_orders(order_list)

        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count

        return jsonify({
            'success': True,
            'data': {
                'total': len(results),
                'success': success_count,
                'failed': fail_count,
                'results': results
            }
        })

    except Exception as e:
        logger.error(f"执行订单失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'Fibonacci Pyramid Trading System'
    })


@app.route('/api/history', methods=['GET'])
def get_order_history():
    """
    获取订单历史记录

    查询参数:
    - limit: 返回数量（默认10）
    - stock_code: 筛选特定股票
    """
    try:
        limit = int(request.args.get('limit', 10))
        stock_code = request.args.get('stock_code', '').strip()

        if stock_code:
            orders = storage.get_orders_by_stock(stock_code)
        else:
            orders = storage.get_recent_orders(limit)

        return jsonify({
            'success': True,
            'data': {
                'orders': orders,
                'count': len(orders)
            }
        })

    except Exception as e:
        logger.error(f"获取历史记录失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取统计信息"""
    try:
        stats = storage.get_statistics()

        return jsonify({
            'success': True,
            'data': stats
        })

    except Exception as e:
        logger.error(f"获取统计信息失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/order/<order_id>', methods=['GET'])
def get_order_detail(order_id: str):
    """
    获取订单详情

    路径参数:
    - order_id: 订单ID
    """
    try:
        order = storage.get_order_by_id(order_id)

        if order is None:
            return jsonify({
                'success': False,
                'message': '订单不存在'
            }), 404

        return jsonify({
            'success': True,
            'data': order
        })

    except Exception as e:
        logger.error(f"获取订单详情失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route('/api/order/<order_id>', methods=['DELETE'])
def delete_order(order_id: str):
    """
    删除订单记录

    路径参数:
    - order_id: 订单ID
    """
    try:
        success = storage.delete_order(order_id)

        if not success:
            return jsonify({
                'success': False,
                'message': '订单不存在'
            }), 404

        return jsonify({
            'success': True,
            'message': '订单已删除'
        })

    except Exception as e:
        logger.error(f"删除订单失败: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', config.PORT))
    app.run(host=config.HOST, port=port, debug=config.DEBUG)
