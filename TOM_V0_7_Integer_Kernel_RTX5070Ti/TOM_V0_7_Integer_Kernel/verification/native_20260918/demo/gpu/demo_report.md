# A plan can be corrected without rewriting its past

A small guarded revision-history demo using the full source TOM expression and a real native runner.

The caller chooses every guard, plan value, result symbol and order tag. These are demonstration inputs, not dynamics or observations selected by TOM.

| Step | Result | Before | Proposed | Kept |
| --- | --- | --- | --- | --- |
| Start with the source definition | ADMITTED | Empty. | Full TOM source definition. | Full TOM source definition. |
| Wait for the caller's condition | PENDING_GUARD | Full TOM source definition. | Full TOM source definition. / Paint the door blue. | Full TOM source definition. |
| Accept the supplied revision | ADMITTED | Full TOM source definition. | Full TOM source definition. / Paint the door blue. | Full TOM source definition. / Paint the door blue. |
| Reject editing the accepted past | PREFIX_REWRITE | Full TOM source definition. / Paint the door blue. | Full TOM source definition. / Paint the door teal. | Full TOM source definition. / Paint the door blue. |
| Append a correction | ADMITTED | Full TOM source definition. / Paint the door blue. | Full TOM source definition. / Paint the door blue. / Later correction: Paint the door teal. Earlier blue plan retained. | Full TOM source definition. / Paint the door blue. / Later correction: Paint the door teal. Earlier blue plan retained. |

1. The full source is admitted. A named later continuation is declared, without consuming a future result.
2. The caller proposes a blue plan, but the supplied guard is false. Nothing is added to completed history.
3. The caller now supplies a met guard and the blue result. The revision is appended after the existing source commitment.
4. Changing the existing blue bytes to teal is rejected, even though their lengths match and the guard is met. The candidate result is blocked.
5. The caller appends a teal correction. Both the earlier blue commitment and the later correction remain visible in order.

Every step was checked against the independent Python reference: 2,980 result words matched.
Each continuation reads the preceding runner output file, including its committed history. A rejected attempt adds no history entry. The earlier accepted bytes survive both the failed overwrite and the legal correction.

Each attempt uses a later external order tag. Its previous tag remains the last committed tag, so elapsed time includes rejected attempts. The runner reexecutes and validates the actual prior result through --resume before accepting a continuation.

JSON Lines is an explicitly chosen external history codec. The native engine compares and preserves its complete bytes; it does not assign meaning to the plan text.
