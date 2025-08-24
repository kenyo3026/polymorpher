import os
from typing import List
from pathlib import Path


class PathTreeNode:
    def __init__(self, name, is_leaf=False):
        self.name = name
        self.is_leaf = is_leaf
        self.children = {}

    def add_child(self, child_name, is_leaf=False):
        if child_name not in self.children:
            self.children[child_name] = PathTreeNode(child_name, is_leaf)
        return self.children[child_name]

    def concentrate(self):
        while len(self.children) == 1 and not any(child.is_leaf for child in self.children.values()):
            child = list(self.children.values())[0]
            self.name = os.path.join(self.name, child.name)
            self.children = child.children

        for child in self.children.values():
            child.concentrate()


class PathTree:
    def __init__(self):
        self.root = None

    def add_path(self, path_parts):
        if self.root is None:
            self.root = PathTreeNode(path_parts[0])

        current_node = self.root
        if path_parts[0] == self.root.name:
            path_parts = path_parts[1:]

        for i, part in enumerate(path_parts):
            is_leaf = (i == len(path_parts) - 1)
            current_node = current_node.add_child(part, is_leaf)

    def traverse(self, node=None):
        if node is None:
            node = self.root
        result = [node.name]
        for child in sorted(node.children.values(), key=lambda x: x.name):
            result.extend(self.traverse(child))
        return result

    def format(self, node=None, prefix=""):
        if node is None:
            node = self.root

        formatted_str = prefix + ("└── " if prefix else "") + node.name + "\n"

        children = sorted(node.children.values(), key=lambda x: x.name)
        for i, child in enumerate(children):
            formatted_str += self.format(child, prefix + "    ")
        return formatted_str

    def display(self, **kwargs):
        print(self.format(**kwargs))


class TreeGraph:

    @classmethod
    def from_paths(
        cls,
        paths:List[str],
        concentrate:bool=True,
    ):
        tree = PathTree()
        for path in paths:
            if isinstance(path, str):
                path = list(Path(path).parts)
            tree.add_path(path)

        if concentrate:
            tree.root.concentrate()

        return tree


if __name__ == '__main__':
    paths = [
        '/home/kenyo/Desktop/workspace/llm-tools/.gitignore',
        '/home/kenyo/Desktop/workspace/llm-tools/.gitlab-ci.yml',
        '/home/kenyo/Desktop/workspace/llm-tools/conftest.py',
        '/home/kenyo/Desktop/workspace/llm-tools/docker-build.sh',
        '/home/kenyo/Desktop/workspace/llm-tools/insert_db.py',
        '/home/kenyo/Desktop/workspace/llm-tools/requirements-for-unittest.txt',
        '/home/kenyo/Desktop/workspace/llm-tools/requirements-to-freeze.txt',
        '/home/kenyo/Desktop/workspace/llm-tools/requirements.txt',
        '/home/kenyo/Desktop/workspace/llm-tools/test_pytest.py',
        '/home/kenyo/Desktop/workspace/llm-tools/tools/jira/jira2/core_router.py',
        '/home/kenyo/Desktop/workspace/llm-tools/tools/jira/jira2/core_router_for_prosuite.py',
        '/home/kenyo/Desktop/workspace/llm-tools/tools/jira/tools/parser_with_ai.py',
        '/home/kenyo/Desktop/workspace/llm-tools/tools/utils/mongo.py'
    ]

    tree = TreeGraph.from_paths(paths, concentrate=False)
    tree.display()

    tree = TreeGraph.from_paths(paths, concentrate=True)
    tree.display()