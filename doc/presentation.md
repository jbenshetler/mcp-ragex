# `ragex` : Semantic Search for Code with a an MCP Interface
by Jeff Benshetler

2025-09-10

## Introduction
In January of 2025, along with many others, I began using coding agents. Most of my time was spent in Claude Code. This was started as a learning experience, a way to become familiar with and evaluate a new tool. Rather than apply this in a vacuum, I started work on a personal project.

I learn best by application. I want to more easily locate files from my hard drive and am not satisfied with existing commercial or open source solutions. So, for a couple of years I had been off-and-on playing with ElasticSearch. However, I had only been able to create a partially working solution that was later sabotaged by a licensing change. To do this, I pivoted to OpenSearch used Claude Code to help with the configuration. Over time, this grew into a much larger project due to external interest. 

While I was pleased with the help Claude Code provided, I was stymied by the dreaded `Compacting Conversation`, delayed by the slow `Seaching` tools calls, and frustrated by how often it would recreate existing functionality. When Claude Code added support for in April, 2025, I decided to do something about this. 

## Requirements
1. Speed regular expression searches
1. Support semantic searches
1. Callable by MCP

## Design Decisions
1. Use `ripgrep` to support fast regular expression searches.

### Regex searching
Claude Code's default is to use regular expressions to search. When I created this tool, Claude used `grep`, which is slow. My first effort was adding support for `ripgrep`, which performs parallel searches. 
### Semantic searching
In my usage, Claude regularly re-creates existing functionality in non-trivial code, likely due to not only a limited context window but also context rot. Beyond the searching being slow, the coding agent's review is slow and consumes a large number of tokens, compounding the forgetting problem. 
## Challenges
### TokensYou 
### Security
Users righfully have security concerns. 
#### Model

## References
1. "Context Rot: How Increasing Input Tokens Impacts LLM Performance" by Kelly Hong, Anton Troynikov, and Jeff Huber, https://research.trychroma.com/context-rot
1. Claude Code Release Notes, https://claudelog.com/faqs/claude-code-release-notes/
1. 