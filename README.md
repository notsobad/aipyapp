# Python use
Python use (aipython) is a Python command-line interpreter integrated with LLM.

## What
Python use provides the entire Python execution environment for LLM to use. You can imagine LLM sitting in front of a computer, typing various commands in the Python command-line interpreter, pressing enter to run them, observing the results, and then typing and executing more code.

The difference from Agent is that Python use does not define any tools interface, allowing LLM to freely use all the features provided by the Python runtime environment.

## Why
If you are a data engineer, you are probably familiar with the following scenarios:
- Handling various data files in different formats: csv/excel, json, html, sqlite, parquet ...
- Performing operations such as data cleaning, transformation, computation, aggregation, sorting, grouping, filtering, analysis, and visualization

This process often requires:
- Starting Python, importing pandas as pd, and typing a bunch of commands to process data
- Generating a bunch of intermediate temporary files
- Describing your needs to ChatGPT / Claude, copying the generated data processing code, and running it manually

So, why not start the Python command-line interpreter, describe your data processing needs directly, and have it done automatically? The benefits are:
- No need to manually input a bunch of Python commands temporarily
- No need to describe your needs to GPT, copy the program, and run it manually

This is the problem that Python use aims to solve!

## How
Python use (aipython) is a Python command-line interpreter integrated with LLM. You can:
- Input and execute Python commands as usual
- Describe your needs in natural language, and aipython will automatically generate and execute Python commands

Moreover, the two modes can access data interchangeably. For example, after aipython processes your natural language commands, you can use standard Python commands to view various data.

## TODO
- Too many issues to handle

## Thanks
- Sonnet 3.7: Generated the first version of the code, which was almost ready to use without modification.
- ChatGPT: Provided many suggestions and code snippets, especially for the command-line interface.
- Codeium: Intelligent code completion
- Copilot: Code improvement suggestions



