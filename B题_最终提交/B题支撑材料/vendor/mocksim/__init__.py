# -*- coding: utf-8 -*-
"""mocksim -- CUMCM 2026 B 题 本地测试环境 (按公开协议规范实现, 非官方模拟器).

模块
----
arena   : 物理规则 / 虚拟计时 / 案例生成 (附录1、附录2 的常数)
server  : HTTP+JSON 接口 /enter /measure /clear /exit (附件2)
client  : 参考机器狗客户端 (urllib, 逐次等待响应, request_id 幂等重试)
harness : 演练批量运行、统计、表1 结果导出、明文行为日志
conformance : 协议一致性自测套件 (校验任意客户端是否符合附件2)
"""

from . import arena

__all__ = ["arena"]
__version__ = "1.0.0"
