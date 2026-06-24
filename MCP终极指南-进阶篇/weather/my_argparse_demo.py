#!/usr/bin/env python3
import argparse

def main():
    # 创建解析器
    parser = argparse.ArgumentParser(
        description='这是一个示例命令行工具，演示argparse的基本用法',
        epilog='更多信息请访问 https://example.com'
    )
    
    # ============ 位置参数（必填） ============
    parser.add_argument(
        'name',                    # 参数名
        help='你的名字（位置参数，必填）'
    )
    
    # ============ 可选参数（短选项+长选项） ============
    parser.add_argument(
        '-a', '--age',             # 短选项和长选项
        type=int,                  # 指定类型
        default=18,                # 默认值
        help='你的年龄（默认：18）'
    )
    
    parser.add_argument(
        '-c', '--city',
        choices=['北京', '上海', '深圳', '杭州'],  # 限定可选值
        help='你所在的城市（可选）'
    )
    
    # ============ 布尔标志（action='store_true'） ============
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',       # 如果出现则设为True，否则False
        help='显示详细信息'
    )
    
    # ============ 列表参数（nargs='*' 零个或多个） ============
    parser.add_argument(
        '--hobby',
        nargs='*',                 # 接收零个或多个值
        default=['编程'],          # 默认值
        help='你的爱好（可多个，空格分隔）'
    )
    
    # ============ 必须的可选参数（required=True） ============
    parser.add_argument(
        '-e', '--email',
        required=True,             # 必须提供
        help='你的邮箱（必填）'
    )
    
    # ============ 互斥组 ============
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--with-pet',
        action='store_true',
        help='带着宠物'
    )
    group.add_argument(
        '--without-pet',
        action='store_true',
        help='不带宠物'
    )
    
    # 解析参数
    args = parser.parse_args()
    
    # ============ 使用参数 ============
    if args.verbose:
        print(f"🔍 调试信息:")
        print(f"   {args}")
    
    print(f"\n👋 你好，{args.name}！")
    
    if args.age:
        print(f"📅 年龄：{args.age}岁")
    
    if args.city:
        print(f"📍 城市：{args.city}")
    
    if args.email:
        print(f"📧 邮箱：{args.email}")
    
    # 处理爱好（多个）
    hobbies = ', '.join(args.hobby)
    print(f"🎯 爱好：{hobbies}")
    
    # 处理互斥组
    if args.with_pet:
        print("🐕 带着宠物")
    elif args.without_pet:
        print("🚫 不带宠物")
    else:
        print("❓ 未说明是否带宠物")
    
    print(f"\n✅ 程序运行完成！")

if __name__ == '__main__':
    main()