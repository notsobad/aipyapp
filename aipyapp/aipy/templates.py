
CONSOLE_HTML_FORMAT = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
.r1 {{color: #008080; text-decoration-color: #008080; font-weight: bold}}
.r2 {{color: #800000; text-decoration-color: #800000; font-weight: bold}}
.r3 {{color: #008000; text-decoration-color: #008000}}
.r4 {{color: #008000; text-decoration-color: #008000; font-weight: bold}}
.r5 {{color: #800080; text-decoration-color: #800080}}
.r6 {{color: #ff00ff; text-decoration-color: #ff00ff}}
.r7 {{color: #008080; text-decoration-color: #008080}}
.r8 {{color: #808000; text-decoration-color: #808000}}
.r9 {{color: #800000; text-decoration-color: #800000}}
.r10 {{color: #008080; text-decoration-color: #008080; background-color: #ffffff; font-weight: bold}}
.r11 {{background-color: #ffffff}}
.r12 {{color: #444444; text-decoration-color: #444444; background-color: #ffffff}}
.r13 {{color: #cc3366; text-decoration-color: #cc3366; background-color: #ffffff}}
.r14 {{color: #222222; text-decoration-color: #222222; background-color: #ffffff}}
.r15 {{color: #006699; text-decoration-color: #006699; background-color: #ffffff}}
.r16 {{color: #228822; text-decoration-color: #228822; background-color: #ffffff}}
.r17 {{color: #aa9900; text-decoration-color: #aa9900; background-color: #ffffff}}
.r18 {{color: #6633cc; text-decoration-color: #6633cc; background-color: #ffffff}}
.r19 {{color: #808000; text-decoration-color: #808000; font-weight: bold}}
.r20 {{color: #333333; text-decoration-color: #333333; background-color: #ffffff; font-weight: bold}}
.r21 {{color: #999999; text-decoration-color: #999999; background-color: #ffffff}}
.r22 {{color: #222222; text-decoration-color: #222222}}
.r23 {{font-weight: bold}}
body {{
    color: #000000;
    background-color: #ffffff;
}}
</style>
</head>
<body>
    <pre style="font-family:Menlo,'DejaVu Sans Mono',consolas,'Courier New',monospace"><code style="font-family:inherit">{code}</code></pre>
</body>
</html>
"""

DISCLAIMER_TEXT = """[bold yellow]⚠️  风险提示与免责声明 ⚠️[/bold yellow]

本程序会执行由大型语言模型（LLM）自动生成的代码。请您在继续使用前，务必阅读并理解以下内容：

[bold red]1. 风险提示：[/bold red]
- 自动生成的代码可能包含逻辑错误、性能问题或不安全操作（如删除文件、访问网络、执行系统命令等）。
- 本程序无法保证生成代码的准确性、完整性或适用性。
- 在未充分审查的情况下运行生成代码，可能会对您的系统、数据或隐私造成损害。

[bold yellow]2. 免责声明：[/bold yellow]
- 本程序仅作为开发与测试用途提供，不对由其生成或执行的任何代码行为承担责任。
- 使用本程序即表示您理解并接受所有潜在风险，并同意对因使用本程序产生的任何后果自行负责。"""
