#!/usr/bin/env python3
"""
机器学习优化功能演示脚本

展示机器学习预测和自适应优化的核心功能
"""

import time
import random
import numpy as np
import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app.core.ml_optimization import (
        get_ml_performance_monitor,
        get_ml_predictions,
        get_ml_optimized_config,
        get_ml_anomalies,
        set_ml_optimization_strategy,
        OptimizationStrategy,
        PerformanceMetrics,
    )
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保在正确的目录下运行演示脚本")
    sys.exit(1)


def print_separator(title: str):
    """打印分隔符"""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_metrics(metrics: PerformanceMetrics):
    """打印性能指标"""
    print(f"时间戳: {datetime.fromtimestamp(metrics.timestamp)}")
    print(f"缓存命中率: {metrics.cache_hit_rate:.2%}")
    print(f"响应时间: {metrics.response_time:.2f}ms")
    print(f"内存使用率: {metrics.memory_usage:.2%}")
    print(f"CPU使用率: {metrics.cpu_usage:.2%}")
    print(f"错误率: {metrics.error_rate:.2%}")
    print(f"QPS: {metrics.qps:.0f}")
    print(f"锁超时率: {metrics.lock_timeout_rate:.2%}")
    print(f"连接池使用率: {metrics.connection_pool_usage:.2%}")


def print_predictions(predictions):
    """打印预测结果"""
    if not predictions:
        print("暂无预测数据")
        return

    print(f"预测结果 (共{len(predictions)}项):")
    for i, pred in enumerate(predictions, 1):
        print(f"\n{i}. {pred['metric_name'].upper()}")
        print(f"   当前值: {pred['current_value']:.4f}")
        print(f"   预测值: {pred['predicted_value']:.4f}")
        print(f"   置信度: {pred['confidence']:.2%}")
        print(f"   趋势: {pred['trend']}")
        print(f"   建议: {pred['recommendation']}")
        print(f"   紧急程度: {pred['urgency_level']}")


def print_optimized_config(config):
    """打印优化配置"""
    print("优化后的配置:")
    for key, value in config.items():
        print(f"  {key}: {value}")


def print_anomalies(anomalies):
    """打印异常检测结果"""
    if not anomalies:
        print("未检测到异常")
        return

    print(f"异常检测结果 (共{len(anomalies)}项):")
    for i, anomaly in enumerate(anomalies, 1):
        print(f"\n{i}. {anomaly['metric'].upper()}")
        print(f"   异常值: {anomaly['value']:.4f}")
        print(
            f"   预期范围: {anomaly['expected_range'][0]:.4f} - {anomaly['expected_range'][1]:.4f}"
        )
        print(f"   Z-score: {anomaly['z_score']:.2f}")
        print(f"   严重程度: {anomaly['severity']}")
        print(f"   检测时间: {datetime.fromtimestamp(anomaly['timestamp'])}")


def simulate_performance_data(duration: int = 60, interval: int = 5):
    """模拟性能数据收集"""
    print_separator("开始性能数据模拟")
    print(f"模拟时长: {duration}秒")
    print(f"数据间隔: {interval}秒")

    monitor = get_ml_performance_monitor()

    # 设置优化策略
    strategies = [
        OptimizationStrategy.CONSERVATIVE,
        OptimizationStrategy.ADAPTIVE,
        OptimizationStrategy.AGGRESSIVE,
    ]
    current_strategy = 0

    start_time = time.time()
    data_points = 0

    try:
        while time.time() - start_time < duration:
            # 模拟不同的性能场景
            scenario = (data_points // 10) % 4  # 每10个数据点切换场景

            if scenario == 0:
                # 正常性能
                cache_hit_rate = 0.85 + random.normalvariate(0, 0.02)
                response_time = 50 + random.normalvariate(0, 5)
                memory_usage = 0.6 + random.normalvariate(0, 0.05)
                error_rate = 0.01 + random.normalvariate(0, 0.002)
                qps = 1000 + random.normalvariate(0, 50)
            elif scenario == 1:
                # 性能下降
                cache_hit_rate = 0.6 + random.normalvariate(0, 0.05)
                response_time = 200 + random.normalvariate(0, 20)
                memory_usage = 0.8 + random.normalvariate(0, 0.05)
                error_rate = 0.05 + random.normalvariate(0, 0.01)
                qps = 500 + random.normalvariate(0, 100)
            elif scenario == 2:
                # 性能异常
                cache_hit_rate = 0.3 + random.normalvariate(0, 0.1)
                response_time = 500 + random.normalvariate(0, 50)
                memory_usage = 0.95 + random.normalvariate(0, 0.02)
                error_rate = 0.1 + random.normalvariate(0, 0.02)
                qps = 200 + random.normalvariate(0, 50)
            else:
                # 性能恢复
                cache_hit_rate = 0.9 + random.normalvariate(0, 0.02)
                response_time = 30 + random.normalvariate(0, 3)
                memory_usage = 0.5 + random.normalvariate(0, 0.03)
                error_rate = 0.005 + random.normalvariate(0, 0.001)
                qps = 1500 + random.normalvariate(0, 100)

            # 创建性能指标
            metrics = PerformanceMetrics(
                timestamp=time.time(),
                cache_hit_rate=max(0, min(1, cache_hit_rate)),
                response_time=max(0, response_time),
                memory_usage=max(0, min(1, memory_usage)),
                cpu_usage=0.3 + random.normalvariate(0, 0.1),
                error_rate=max(0, min(1, error_rate)),
                qps=max(0, qps),
                lock_timeout_rate=0.02 + random.normalvariate(0, 0.01),
                connection_pool_usage=0.7 + random.normalvariate(0, 0.1),
            )

            # 更新预测器
            monitor.predictor.add_performance_data(metrics)

            # 更新优化器
            monitor.optimizer.update_performance_metrics(metrics)

            # 检测异常
            anomalies = monitor.anomaly_detector.detect_anomalies(metrics)
            data_points += 1

            # 每10个数据点切换优化策略
            if data_points % 10 == 0:
                current_strategy = (current_strategy + 1) % len(strategies)
                monitor.set_optimization_strategy(strategies[current_strategy])
                print(f"\n切换到优化策略: {strategies[current_strategy].value}")

            # 每5个数据点显示当前状态
            if data_points % 5 == 0:
                print(f"\n数据点 {data_points}:")
                print_metrics(metrics)

                # 显示预测结果
                predictions = monitor.get_predictions()
                if predictions:
                    print("\n预测结果:")
                    for pred in predictions[:3]:  # 只显示前3个预测
                        print(
                            f"  {pred.metric_name}: {pred.trend} ({pred.urgency_level})"
                        )

                # 显示优化配置
                config = monitor.get_optimized_config()
                print(
                    f"\n当前优化配置: 连接池={config['connection_pool_size']}, "
                    f"超时={config['socket_timeout']:.2f}s"
                )

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n模拟被用户中断")

    print(f"\n模拟完成，共收集 {data_points} 个数据点")


def demonstrate_predictions():
    """演示预测功能"""
    print_separator("机器学习预测功能演示")

    # 获取预测结果
    predictions = get_ml_predictions()
    print_predictions(predictions)

    # 分析预测趋势
    if predictions:
        critical_predictions = [
            p for p in predictions if p["urgency_level"] in ["high", "critical"]
        ]
        if critical_predictions:
            print(f"\n⚠️  发现 {len(critical_predictions)} 个高优先级预测:")
            for pred in critical_predictions:
                print(f"  - {pred['metric_name']}: {pred['recommendation']}")


def demonstrate_optimization():
    """演示优化功能"""
    print_separator("自适应优化功能演示")

    # 获取优化配置
    config = get_ml_optimized_config()
    print_optimized_config(config)

    # 获取优化历史
    monitor = get_ml_performance_monitor()
    history = monitor.get_optimization_history()

    if history:
        print(f"\n优化历史 (共{len(history)}次):")
        for i, record in enumerate(history[-5:], 1):  # 显示最近5次
            print(f"\n{i}. 时间: {datetime.fromtimestamp(record['timestamp'])}")
            print(f"   策略: {record['strategy']}")
            print(f"   优化计划: {record['optimization_plan']}")
    else:
        print("\n暂无优化历史")


def demonstrate_anomaly_detection():
    """演示异常检测功能"""
    print_separator("异常检测功能演示")

    # 获取异常检测结果
    anomalies = get_ml_anomalies()
    print_anomalies(anomalies)

    # 分析异常趋势
    if anomalies:
        critical_anomalies = [
            a for a in anomalies if a["severity"] in ["high", "critical"]
        ]
        if critical_anomalies:
            print(f"\n🚨 发现 {len(critical_anomalies)} 个严重异常:")
            for anomaly in critical_anomalies:
                print(f"  - {anomaly['metric']}: {anomaly['value']:.4f}")


def demonstrate_strategy_comparison():
    """演示不同优化策略的对比"""
    print_separator("优化策略对比演示")

    strategies = [
        ("保守策略", OptimizationStrategy.CONSERVATIVE),
        ("自适应策略", OptimizationStrategy.ADAPTIVE),
        ("激进策略", OptimizationStrategy.AGGRESSIVE),
    ]

    for name, strategy in strategies:
        print(f"\n{name}:")
        set_ml_optimization_strategy(strategy.value)

        # 获取当前配置
        config = get_ml_optimized_config()
        print(f"  连接池大小: {config['connection_pool_size']}")
        print(f"  Socket超时: {config['socket_timeout']:.2f}s")
        print(f"  锁超时: {config['lock_timeout']:.2f}s")
        print(f"  批处理大小: {config['batch_size']}")
        print(f"  缓存大小: {config['cache_max_size']}")


def main():
    """主函数"""
    print("🤖 机器学习预测和自适应优化演示")
    print("=" * 60)

    try:
        # 1. 性能数据模拟
        simulate_performance_data(duration=30, interval=3)

        # 2. 预测功能演示
        demonstrate_predictions()

        # 3. 优化功能演示
        demonstrate_optimization()

        # 4. 异常检测演示
        demonstrate_anomaly_detection()

        # 5. 策略对比演示
        demonstrate_strategy_comparison()

        print_separator("演示完成")
        print("✅ 机器学习优化功能演示完成")
        print("📊 系统已自动收集性能数据并进行优化")
        print("🔍 可通过日志查看详细的优化过程")

    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
