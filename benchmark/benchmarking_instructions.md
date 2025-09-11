# Benchmarking ragex
The goal is to compare the performance of semantic search with `grep` and `ripgrep`. The older `grep` approach is included even though no longer current because it was what was used when semantic search was created. 

Ensure that `ragex` is installed and started for the directory under test. 

Empty `CLAUDE.md` before starting the test. 


## Benchmark
```
BENCHMARK_RUN_DIR=$(pwd)
BENCHMARK_DATA_DIR=${BENCHMARK_RUN_DIR}/output
mkdir ${BENCHMARK_DATA_DIR}
mkdir -p ${BENCHMARK_DATA_DIR}/{grep,ripgrep,ragex}
LOG_DIR=$(echo ~/.claude/projects/$(pwd | perl -lne 's/\//-/g; print'))
N=12

cd ${BENCHMARK_RUN_DIR}
echo "search_tool,timestamp,input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens,service_tier,ephemeral_5m_input_tokens,ephemeral_1h_input_tokens" > output/search_benchmarks.csv

####################
# Ragex

# Capture
cd ${BENCHMARK_RUN_DIR}
ragex register claude | bash
for i in {1..$N}; do (time cat doc/benchmark.claude | claude -p >> output/ragex.log) 2>> output/ragex_time.log; echo $i; done
ragex unregister claude | bash

# Gather
cd ${LOG_DIR}
ls -ltrh *.jsonl | tail -n $N  | perl -alne 'print $F[-1]' | xargs -I {} cp -a {} ${BENCHMARK_RUN_DIR}/ragex


####################
# Ripgrep

# Capture
cd ${BENCHMARK_RUN_DIR}
for i in {1..$N}; do (time cat doc/benchmark.claude | claude -p >> output/ripgrep.log) 2>> output/ripgrep_time.log; echo $i; done

# Gather
cd ${LOG_DIR}
ls -ltrh *.jsonl | tail -n $N  | perl -alne 'print $F[-1]' | xargs -I {} cp -a {} ${BENCHMARK_RUN_DIR}/ripgrep

####################
# grep

# Capture
cd ${BENCHMARK_RUN_DIR}
for i in {1..$N}; do (time cat doc/benchmark.claude | claude -p >> output/grep.log) 2>> output/grep_time.log; echo $i; done

# Gather
cd ${LOG_DIR}
ls -ltrh *.jsonl | tail -n $N  | perl -alne 'print $F[-1]' | xargs -I {} cp -a {} ${BENCHMARK_RUN_DIR}/grep


##############
# Extract

cd ${BENCHMARK_DATA_DIR}
echo "search_tool,timestamp,input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens,service_tier,ephemeral_5m_input_tokens,ephemeral_1h_input_tokens" > search_benchmarks.csv

for treatment in grep ripgrep ragex; do
    jq --arg treatment "$treatment" -r 'select(.message.content | type == "array" and length > 0 and .[0].type == "tool_use") |
        [$treatment,
        .sessionId,
        .timestamp,
        .message.usage.input_tokens,
        .message.usage.cache_creation_input_tokens,
        .message.usage.cache_read_input_tokens,
        .message.usage.output_tokens,
        .message.usage.service_tier,
        .message.usage.cache_creation.ephemeral_5m_input_tokens,
        .message.usage.cache_creation.ephemeral_1h_input_tokens] |
        @csv' *.jsonl >> search_benchmarks.csv

done



```


## Below here is old stuff that did work but has not been integrated with the stuff at the top. 

## Ripgrep

```
## Grep
for i in {1..12}; do (time cat doc/benchmark.claude | USE_BUILTING_RIPGREP=0 claude -p >> grep.log) 2>> grep_time.log; echo $i; done
```

```
echo "search_tool,timestamp,input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens,service_tier,ephemeral_5m_input_tokens,ephemeral_1h_input_tokens"
```

```
jq -r 'select(.message.content | type == "array" and length > 0 and .[0].type == "tool_use") |
  [ "ragex",
    .timestamp,
   .message.usage.input_tokens,
   .message.usage.cache_creation_input_tokens,
   .message.usage.cache_read_input_tokens,
   .message.usage.output_tokens,
   .message.usage.service_tier,
   .message.usage.cache_creation.ephemeral_5m_input_tokens,
   .message.usage.cache_creation.ephemeral_1h_input_tokens] |
  @csv' 0b9b0f3a-ba23-4a2a-8c7e-c16c8baaad42.jsonl
```

  
```
# Write headers including sessionId
echo "treatment,session_id,timestamp,input_tokens,cache_creation_input_tokens,cache_read_input_tokens,output_tokens,service_tier,ephemeral_5m_input_tokens,ephemeral_1h_input_tokens" > output.csv
```

```
# Extract data with sessionId
jq -r 'select(.message.content | type == "array" and length > 0 and .[0].type == "tool_use") |
  ["ragex",
   .sessionId,
   .timestamp,
   .message.usage.input_tokens,
   .message.usage.cache_creation_input_tokens,
   .message.usage.cache_read_input_tokens,
   .message.usage.output_tokens,
   .message.usage.service_tier,
   .message.usage.cache_creation.ephemeral_5m_input_tokens,
   .message.usage.cache_creation.ephemeral_1h_input_tokens] |
  @csv' 0b9b0f3a-ba23-4a2a-8c7e-c16c8baaad42.jsonl >> output.csv
  ```