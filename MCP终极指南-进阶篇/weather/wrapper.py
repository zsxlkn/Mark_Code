import argparse
import subprocess
import sys

def main():
    parser = argparse.ArgumentParser(
        description='一个命令包装器，可以执行任意命令'
    )
    
    # 自己的选项
    parser.add_argument('-v', '--verbose', 
                        action='store_true',
                        help='显示详细输出')
    
    parser.add_argument('--timeout',
                        type=int,
                        default=30,
                        help='超时时间（秒）')
    
    # 使用 REMAINDER 捕获命令及其所有参数
    parser.add_argument('command', 
                        nargs=argparse.REMAINDER,
                        help='要执行的命令及其参数')
    
    args = parser.parse_args()
    
    if args.verbose:
        print(f"🔍 详细模式开启")
        print(f"⏱️  超时: {args.timeout}秒")
        print(f"📋 命令: {args.command}")
    
    if not args.command:
        print("❌ 错误：请提供要执行的命令")
        print(f"用法: {sys.argv[0]} [选项] <命令> [参数...]")
        return
    
    # 执行捕获的命令
    print(f"🚀 执行: {' '.join(args.command)}")
    result = subprocess.run(args.command)
    
    print(f"✅ 命令退出码: {result.returncode}")

if __name__ == '__main__':
    main()