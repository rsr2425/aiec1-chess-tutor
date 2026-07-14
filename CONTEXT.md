# Ubiquitous Language

Glossary for the chess tutor agent (Certification Challenge project).

## Terms

### Student
The target user: an adult chess improver (under ~1500 chess.com rating) who
wants to improve, cannot afford or does not want a human coach, and is willing
to invest real time and effort in reviewing their own games.

### Annotated Game
A single chess game in PGN form that includes the Student's own written
thoughts (PGN comments) describing what they were thinking during play — plans,
fears, evaluations, candidate moves. Distinct from an engine-annotated PGN,
whose comments come from a machine.

### Annotation
One of the Student's written thoughts attached to a specific move in an
Annotated Game. The raw material the tutor uses to understand the Student's
thought process, as opposed to merely their moves.

### Bare Game
A PGN with moves but no Annotations. Accepted in a degraded "moves-only" mode:
the tutor can still review the moves, but cannot coach the Student's thought
process. The Annotated Game is the primary, designed-for input.

### Takeaway
One of the 2–3 key points the tutor distills for the Student immediately after
a game upload. Grounded in the current game but informed by the Student's
Lessons (long-term memory). Ephemeral: it belongs to that game's review.

### Lesson
A persistent, recurring theme in a Student's play ("evaluates threats without
checking for pins"), accumulated across all uploaded games. Each Lesson has a
recurrence count — the number of games it has surfaced in — and relevance is
measured by that count. The top ~10 Lessons by recurrence form the tutor's
working picture of the Student.

### Recurrence
The number of distinct games in which a Lesson (or a similar-enough theme) has
appeared. The sole relevance measure for ranking Lessons in the POC.

### Moment
A key position singled out from a Student's game: the position itself, the
move played, the Student's Annotation there (if any), and the engine's
verdict. The tutor writes a natural-language paragraph describing each Moment;
that description is what makes Moments searchable. The unit of
position-level recall ("have I been in trouble like this before?").

### Game Summary
A natural-language paragraph describing one uploaded game as a whole —
opening, story of the game, result, and its Takeaways. The unit of game-level
recall ("show me my games where I lost won positions").

### Library
The corpus of openly licensed instructional chess writing (public-domain
classics, openly licensed wiki books) that the tutor searches and cites to the
Student during a review. Distinct from the Student's own data: the Library is
shared teaching material, not personal history.

### Distillation
The step after a game upload in which the tutor agent produces the game's
Takeaways and curates the Student's Lessons the way a human coach maintains
notes on a student: deciding whether each Takeaway reinforces an existing
Lesson (raising its Recurrence) or starts a new one, and merging, renaming, or
retiring Lessons as its picture of the Student sharpens. Lessons are managed by
the agent's judgment, not by similarity machinery. Lessons are pitched at the
level of a correctable habit — not a broad topic, not a single position.
