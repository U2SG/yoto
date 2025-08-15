#!/usr/bin/env python3
"""
测试密码哈希长度
"""

from werkzeug.security import generate_password_hash


def test_password_hash_length():
    """测试不同密码的哈希长度"""
    passwords = [
        "admin123",
        "password123",
        "very_long_password_with_special_chars_!@#$%^&*()",
        "simple",
    ]

    print("测试密码哈希长度:")
    print("=" * 50)

    for password in passwords:
        hash_value = generate_password_hash(password)
        print(f"密码: {password}")
        print(f"哈希长度: {len(hash_value)} 字符")
        print(f"哈希值: {hash_value}")
        print("-" * 30)


if __name__ == "__main__":
    test_password_hash_length()
