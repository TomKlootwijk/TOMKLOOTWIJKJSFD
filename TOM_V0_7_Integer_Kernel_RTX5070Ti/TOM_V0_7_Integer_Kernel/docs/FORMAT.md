# Packed binary formats (all words little-endian uint32)

## Program image `.tsdf`

A 64-byte header comprises sixteen words:

0 magic 0x374D4F54 (`TOM7`); 1 ABI=1; 2 record_words=16; 3 record_count;
4 schedule_offset; 5 schedule_count; 6 binding_offset; 7 binding_count;
8 state_signal_count; 9 temporary_slot_count; 10 kernel_id; 11 time_id;
12 atlas_word_count; 13 flags=0; 14 reserved=0; 15 reserved=0.

All offsets are relative to the start of the word atlas, not file bytes. Atlas:
definition records; 28 kernel microprogram words; scheduled definition ids;
(state_id,value_id) bindings; zero padding to a multiple of sixteen words.
The compiler/loader validate extents, all references used at execution, local
precedence, no duplicate targets, self-addresses and temporary liveness.

A `.map.json` companion supplies readable names and source roles, not runtime
instructions. C++/CUDA can execute the binary image without that map; the Python
readout and case-packing tools use it. A JSON source file is editable input to the
compiler. Native unassigned declarations are present but not executable opcodes.

## Packed data and result `.tsdf`

Magic bytes `TOM7BIT\0`, followed by uint32 state_slots, uint32 lane_words,
uint64 execution_epoch. Payload: state-major uint32 words.
For state slot s and case c, the bit is `(data[s*lane_words+c/32] >> (c%32)) & 1`.
Multi-bit groups list their Boolean fields in low-to-high significance order.
Signed groups use two's complement, with explicit widths in the map.

The magic bytes and role tags distinguish the container contents. Their
payload uses the same raw-bit representation; this does not mean the binary
containers are indistinguishable or that every SDF role has the same semantics.

Explicit data files preserve input cases and execution epoch on resume. A program
and data file must agree on state slots. Padding cases introduced by the host
packer are marked in its report. Runtime output contains allocated lanes, not a
separate assertion that each padding lane was a test case.

## Full trace `.ttrace`

Magic `TOM7TRC\0`; uint32 state_slots; uint32 lane_words; uint64 start_epoch;
uint64 frame_count. Header length is 32 bytes. Then frame_count complete snapshots
of state-major words. Frame zero is the initial state; frame i has epoch
start_epoch+i. The read tool checks exact file length before accessing records.

The trace has no lossy ring overwrite. It may be large. CUDA trace/output exports
the first shard; all shards still execute and their count appears in the report.

## All-shard Boolean mask `.tommask`

`--state-mask-out PATH --state-mask-slot SLOT` exports one selected state plane
across every shard, in global lane order, after measured computation. Header:

| Byte offset | Type | Meaning |
|---|---|---|
| 0 | 8 bytes | Magic `TOM7MSK\0` |
| 8 | uint32 | Selected state slot |
| 12 | uint32 | Format version, currently 1 |
| 16 | uint64 | Total allocated lanes |
| 24 | uint64 | Final execution epoch |

The 32-byte header is followed by little-endian uint32 words, with case `c` in bit
`c % 32` of word `c / 32`. Current lane counts are multiples of 32. The exact file
length is `32 + lanes/8` bytes. This contains one Boolean answer per lane, not the
full multi-plane state, and is not accepted as a resumable `--data` snapshot.
The paired options must be supplied together. Export uses at most a 1 MiB host
transfer buffer and is excluded from compute timing.

`--count-state SLOT` separately reports all-shard Boolean population totals in
JSON, without exporting a mask. `--verify` samples complete states at both ends
of every shard; an independent full-mask comparison requires an external oracle,
as provided by `tools/measure_bounded_space.py` for the bounded TOM profiles.
