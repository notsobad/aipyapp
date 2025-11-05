#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
代码分析和自动修复模块

功能：
1. 检查代码的语法和常见错误（如禁止的导入）
2. 自动修复可修复的错误
3. 生成反馈信息给 LLM
4. 规则可扩展：通过注册 Rule 添加新的检查和修复功能

设计：
- 一次 AST 遍历完成检查和修复，性能最优
- 规则独立，互不影响
- 新增规则只需创建 Rule 子类
"""

from __future__ import annotations
import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from aipyapp.aipy import CodeBlock

@dataclass
class Issue:
    """代表代码中检测到的一个问题"""
    issue_type: str      # "syntax_error", "import_error" 等
    message: str         # 人类可读的描述
    line_no: int = None  # 可选的行号
    fixable: bool = False

    def __str__(self):
        line_info = f" (line {self.line_no})" if self.line_no else ""
        return f"[{self.issue_type}]{line_info}: {self.message}"

@dataclass
class Issues:
    """代码问题集合"""
    issues: List[Issue] = field(default_factory=list)
    num_unfixable: int = 0

    def add_issue(self, issue: Issue) -> None:
        self.issues.append(issue)

    def add(self, issue_type: str, message: str, line_no: int = None, fixable: bool = False) -> None:
        issue = Issue(issue_type, message, line_no, fixable)
        self.issues.append(issue)
        if not fixable:
            self.num_unfixable += 1


class Rule(ABC):
    """代码检查和修复规则的抽象基类"""

    @abstractmethod
    def apply(self, node: ast.AST) -> Tuple[Optional[ast.AST], Optional[Issue]]:
        """
        一步完成：检查节点，如果有问题则修复并返回 Issue

        Args:
            node: AST 节点

        Returns:
            (修复后的节点或 None, 检测到的问题或 None)
            - 如果 node 被删除，返回 (None, Issue 或 None)
            - 如果修复成功，返回 (修复后的节点, Issue)
            - 如果没问题，返回 (原节点, None)
        """
        pass


class ForbiddenImportRule(Rule):
    """检查和移除禁止的导入"""

    FORBIDDEN_IMPORTS = {
        'utils': '不应该 import utils，它已经在全局作用域中可用，直接使用 utils.function() 即可',
    }

    FORBIDDEN_FROM_IMPORTS = {
        ('aipyapp', 'utils'): '不应该 from aipyapp import utils，直接使用全局的 utils 对象即可',
    }

    def apply(self, node: ast.AST) -> Tuple[Optional[ast.AST], Optional[Issue]]:
        """检查并修复导入语句"""

        if isinstance(node, ast.Import):
            return self._handle_import(node)
        elif isinstance(node, ast.ImportFrom):
            return self._handle_import_from(node)

        # 其他节点类型，不处理
        return node, None

    def _handle_import(self, node: ast.Import) -> Tuple[Optional[ast.AST], Optional[Issue]]:
        """处理 import 语句"""
        issue = None
        for alias in node.names:
            if alias.name in self.FORBIDDEN_IMPORTS:
                issue = Issue(
                    issue_type='import_error',
                    message=self.FORBIDDEN_IMPORTS[alias.name],
                    line_no=node.lineno,
                    fixable=True
                )
                break

        # 移除禁止的导入
        new_names = [a for a in node.names if a.name not in self.FORBIDDEN_IMPORTS]

        if not new_names:
            # 整行都被删除
            return None, issue

        if len(new_names) < len(node.names):
            # 部分导入被删除
            node.names = new_names

        return node, issue

    def _handle_import_from(self, node: ast.ImportFrom) -> Tuple[Optional[ast.AST], Optional[Issue]]:
        """处理 from ... import ... 语句"""
        if node.module is None:
            return node, None

        issue = None
        for alias in node.names:
            key = (node.module, alias.name)
            if key in self.FORBIDDEN_FROM_IMPORTS:
                issue = Issue(
                    issue_type='import_error',
                    message=self.FORBIDDEN_FROM_IMPORTS[key],
                    line_no=node.lineno,
                    fixable=True
                )
                break

        # 移除禁止的导入
        new_names = [a for a in node.names
                     if (node.module, a.name) not in self.FORBIDDEN_FROM_IMPORTS]

        if not new_names:
            # 整行都被删除
            return None, issue

        if len(new_names) < len(node.names):
            # 部分导入被删除
            node.names = new_names

        return node, issue


class RuleApplier(ast.NodeTransformer):
    """统一的 AST 遍历器，应用所有规则"""

    def __init__(self, rules: List[Rule], issues: Issues):
        self.rules = rules
        self.issues = issues

    def generic_visit(self, node: ast.AST) -> Optional[ast.AST]:
        """
        重写 generic_visit，在遍历每个节点时应用所有规则
        """
        # 先递归访问子节点（自底向上）
        node = super().generic_visit(node)

        # 然后对当前节点应用所有规则（一次遍历内完成）
        for rule in self.rules:
            node, issue = rule.apply(node)
            if issue:
                self.issues.add_issue(issue)

        return node


class CodeAnalyzer:
    """核心分析器，协调所有规则"""

    def __init__(self):
        self.rules: List[Rule] = []
        self.log = logger.bind(src='CodeAnalyzer')

    def register_rule(self, rule: Rule) -> None:
        """注册一个新的检查规则"""
        self.rules.append(rule)

    def compile(self, block: "CodeBlock") -> None:
        """
        编译代码块，返回是否成功
        """
        if block.co:
            return
        issues = Issues()
        tree = ast.parse(block.code)
        applier = RuleApplier(self.rules, issues)
        tree = applier.visit(tree)
        block.co = compile(tree, block.abs_path or block.name, 'exec')
        for issue in issues.issues:
            self.log.warning(f"Detected issue: {issue}")

    def compile_with_issues(self, block: CodeBlock) -> Issues:
        """
        一次遍历完成：解析 → 应用所有规则 → unparse

        性能：只遍历一遍 AST

        Args:
            code: CodeBlock 对象

        Returns:
            issues: 检测到的问题列表
        """
        issues = Issues()
        # 步骤 1: 解析代码（同时检查语法）
        try:
            tree = ast.parse(block.code)
        except SyntaxError as e:
            # 语法错误不可修复，直接返回
            issues.add(
                issue_type='syntax_error',
                message=f'Syntax error: {e.msg}',
                line_no=e.lineno,
                fixable=False
            )
            return issues

        # 步骤 2: 一次遍历，应用所有规则
        applier = RuleApplier(self.rules, issues)
        tree = applier.visit(tree)

        try:
            block.co = compile(tree, block.abs_path or block.name, 'exec')
        except SyntaxError as e:
            issue = Issue(
                issue_type='syntax_error',
                message=f'Syntax error after fixes: {e.msg}',
                line_no=e.lineno,
                fixable=False
            )
            issues.add_issue(issue)
        return issues

    def get_feedback_for_llm(self, issues: List[Issue]) -> str:
        """
        生成给 LLM 的反馈消息

        Args:
            issues: 检测到的问题列表

        Returns:
            反馈字符串，如果没有问题则返回空字符串
        """
        if not issues:
            return ""

        # 按问题类型分类
        fixable = [i for i in issues if i.fixable]
        unfixable = [i for i in issues if not i.fixable]

        feedback_lines = ["代码分析反馈："]

        if fixable:
            feedback_lines.append("\n✓ 已自动修复的问题：")
            for issue in fixable:
                line_info = f" (第 {issue.line_no} 行)" if issue.line_no else ""
                feedback_lines.append(f"  • {issue.message}{line_info}")

        if unfixable:
            feedback_lines.append("\n✗ 无法修复的问题：")
            for issue in unfixable:
                line_info = f" (第 {issue.line_no} 行)" if issue.line_no else ""
                feedback_lines.append(f"  • {issue.message}{line_info}")

        if fixable:
            feedback_lines.append(
                "\n建议：请改正这些问题，避免下次重复出现相同错误。"
            )

        return "\n".join(feedback_lines)

_code_analyzer = CodeAnalyzer()
_code_analyzer.register_rule(ForbiddenImportRule())

def fix_and_compile(block: CodeBlock) -> Issues:
    """快捷函数：使用全局分析器修复并编译代码块"""
    return _code_analyzer.compile(block)