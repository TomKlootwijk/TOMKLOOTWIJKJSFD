#pragma once
// TOM V0.7 / finite validation realization K1.
// Tom Klootwijk / NL200678942 / date supplied 10-07-1990.
// Logical bits, field clauses and a field-defined evaluator. No numeric geometry.
#include <cstdint>
#if defined(__CUDACC__)
# define TOM_HD __host__ __device__ __forceinline__
#else
# define TOM_HD inline
#endif
namespace tom {
using Word = std::uint32_t;
using Wide = std::uint64_t;
constexpr Word FULL = 0xffffffffu;
constexpr Word RECORD_WORDS = 16;
constexpr Word MAGIC = 0x374d4f54u; // little-endian bytes TOM7
constexpr Word ABI = 1;
enum Kind : Word {
    Kernel = 1, Time = 2, Constant = 3, State = 4, Rule = 5,
    DynamicRule = 6, Expression = 7, Quote = 8, NativeDeclaration = 9
};
struct Header {
    Word magic, abi, record_words, records;
    Word schedule_offset, schedule_count, binding_offset, bindings;
    Word states, scratch_slots, kernel_id, time_id;
    Word atlas_words, flags, reserved0, reserved1;
};
static_assert(sizeof(Header) == 64, "TOM header ABI");
TOM_HD Word all_bits(Word bit) { return Word(0) - (bit & 1u); }
TOM_HD Word choose(Word zero, Word one, Word condition) {
    return zero ^ ((zero ^ one) & condition);
}
// Small physical bootstrap: bit-parallel three-input truth-table evaluation.
// It is NOT claimed to disappear when its law is encoded as an SDF declaration.
TOM_HD Word primitive(Word a, Word b, Word c, Word table) {
    Word p0 = choose(all_bits(table), all_bits(table >> 1), a);
    Word p1 = choose(all_bits(table >> 2), all_bits(table >> 3), a);
    Word p2 = choose(all_bits(table >> 4), all_bits(table >> 5), a);
    Word p3 = choose(all_bits(table >> 6), all_bits(table >> 7), a);
    return choose(choose(p0, p1, b), choose(p2, p3, b), c);
}
TOM_HD Word lowered(Word a, Word b, Word c, const Word* coefficients) {
    return choose(choose(choose(coefficients[0], coefficients[1], a),
                         choose(coefficients[2], coefficients[3], a), b),
                  choose(choose(coefficients[4], coefficients[5], a),
                         choose(coefficients[6], coefficients[7], a), b), c);
}
struct HostReader {
    const Word* atlas;
    const Word* previous;
    TOM_HD Word definition(Word i) const { return atlas[i]; }
    TOM_HD Word data(Word i) const { return previous[i]; }
};
template<class Reader>
TOM_HD Word field(const Reader& r, Word id, Word offset) {
    return r.definition(id * RECORD_WORDS + offset);
}
template<class Reader>
TOM_HD Word value(const Reader& r, const Word* scratch, Word id, Word words, Word lane_word) {
    return scratch[field(r, id, 15) * words + lane_word];
}
// The executable evaluator law is itself stored in the SAME definition atlas.
// 8 coefficient words + 3 input words + 7 temporaries. No register indices here
// are asserted to be ontological nodes, axes or positions in native TOM.
template<class Reader>
TOM_HD Word execute_definition(const Reader& r, const Header& h,
                               Word a, Word b, Word c, const Word* coefficients) {
    Word local[18];
    for (Word i = 0; i < 8; ++i) local[i] = coefficients[i];
    local[8] = a; local[9] = b; local[10] = c;
    const Word base = field(r, h.kernel_id, 1);
    const Word steps = field(r, h.kernel_id, 2);
    const Word selector_table = field(r, h.kernel_id, 3);
    for (Word i = 0; i < steps; ++i) {
        const Word offset = base + i * 4;
        const Word destination = r.definition(offset);
        const Word x = r.definition(offset + 1), y = r.definition(offset + 2);
        const Word condition = r.definition(offset + 3);
        // 0xCA is exactly choose(x,y,condition). Keep reading and executing
        // the stored microprogram, including edited operands and destinations.
        // Other selector laws retain the full truth-table interpretation.
        local[destination] = selector_table == 0xCAu
            ? choose(local[x], local[y], local[condition])
            : primitive(local[x], local[y], local[condition], selector_table);
    }
    return local[field(r, h.kernel_id, 4)];
}
template<bool Lowered, class Reader>
TOM_HD void transition(const Reader& r, Word* scratch, Word* next,
                       const Header& h, Word words, Word lane_word) {
    for (Word index = 0; index < h.schedule_count; ++index) {
        const Word id = r.definition(h.schedule_offset + index);
        const Word kind = field(r, id, 0);
        Word result = 0;
        if (kind == Constant) {
            result = all_bits(field(r, id, 1));
        } else if (kind == State) {
            result = r.data(field(r, id, 1) * words + lane_word);
        } else if (kind == Quote) {
            const Word bit_address = field(r, id, 1);
            result = all_bits(r.definition(bit_address >> 5) >> (bit_address & 31u));
        } else if (kind == Expression) {
            const Word rule = field(r, id, 1);
            const Word a = value(r, scratch, field(r, id, 2), words, lane_word);
            const Word b = value(r, scratch, field(r, id, 3), words, lane_word);
            const Word c = value(r, scratch, field(r, id, 4), words, lane_word);
            Word coefficients[8];
            if (field(r, rule, 0) == Rule) {
                const Word table = field(r, rule, 1);
                for (Word row = 0; row < 8; ++row) coefficients[row] = all_bits(table >> row);
            } else {
                for (Word row = 0; row < 8; ++row)
                    coefficients[row] = value(r, scratch, field(r, rule, row + 1), words, lane_word);
            }
            if constexpr (Lowered) result = lowered(a, b, c, coefficients);
            else result = execute_definition(r, h, a, b, c, coefficients);
        }
        scratch[field(r, id, 15) * words + lane_word] = result;
    }
    // A = T: a stored binding field determines what the next snapshot receives.
    // All values above read the OLD snapshot. No within-launch texture feedback.
    const Word first = field(r, h.time_id, 1);
    const Word count = field(r, h.time_id, 2);
    for (Word i = 0; i < count; ++i) {
        const Word state_id = r.definition(first + 2 * i);
        const Word expression_id = r.definition(first + 2 * i + 1);
        next[field(r, state_id, 1) * words + lane_word] =
            value(r, scratch, expression_id, words, lane_word);
    }
}
TOM_HD Word seed_mix(Word x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu;
    return x ^ (x >> 16);
}
} // namespace tom
