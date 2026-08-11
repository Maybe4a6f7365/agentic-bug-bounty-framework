# Git diff interpretation patterns

## Establish comparison semantics

Verify both endpoints with `git cat-file -e '<sha>^{commit}'`, then inspect `git merge-base`,
`git log --ancestry-path`, tags, and commit parents. Decide whether evidence supports:

- vulnerable release tag to first fixed release tag;
- vulnerable commit/tree to fixed commit/tree;
- single fix commit parent to fix commit;
- pull-request base to head; or
- a merge commit against a specifically justified parent.

Record the chosen endpoints and reason. `A..B` compares trees A and B; it does not mean every
commit in that history is security-relevant. An OSV ecosystem `introduced` value is not
automatically a Git SHA.

## Preserve a reviewable diff

```bash
git -C repo diff --find-renames --find-copies A..B > artifacts/A-to-B.patch
git -C repo diff --name-status --find-renames A..B > artifacts/changed-files.txt
git -C repo diff --stat A..B > artifacts/diff-stat.txt
sha256sum artifacts/A-to-B.patch artifacts/changed-files.txt artifacts/diff-stat.txt
```

Separate security-relevant code, regression tests, generated files, vendored dependencies,
lockfiles, documentation, and unrelated refactors. Follow renamed files before concluding code
was removed or introduced.

## Extract vulnerable versus fixed behavior

For each relevant hunk, capture:

1. attacker-controlled input or state entering the vulnerable path;
2. the trust boundary crossed;
3. the missing, misplaced, or incorrect control in the old tree;
4. the changed validation, authorization, encoding, parsing, or sequencing in the fixed tree;
5. the sensitive operation and observable security oracle;
6. a patched or neighboring safe negative control.

Describe semantics, not merely added lines. A guard may be cosmetic, a refactor may move the real
fix elsewhere, and a dependency bump may hide the relevant patch upstream. Trace calls far enough
to support the root-cause claim and mark inference separately from direct evidence.

## Test-file conventions

Common candidate patterns include:

- JavaScript/TypeScript: `test/`, `tests/`, `__tests__/`, `*.test.js`, `*.spec.ts`;
- Python: `tests/`, `test_*.py`, `*_test.py`;
- Ruby: `spec/`, `test/`, `*_spec.rb`, `test_*.rb`;
- Java/Kotlin: `src/test/java/`, `src/test/kotlin/`, `*Test.java`, `*Tests.kt`;
- Go: `*_test.go`;
- Rust: inline `#[cfg(test)]`, `tests/`, benches used as assertions only after review;
- PHP: `tests/`, `*Test.php`, PHPUnit configuration/suites;
- C/C++: `test/`, `tests/`, `*_test.cc`, framework-specific fixtures;
- C#: `*.Tests/`, `*Tests.cs`, `*Test.cs`.

Names only identify candidates. Fixtures, snapshots, helpers, golden files, and test data may be
important but are not regression tests by themselves.

## Identify the regression oracle

Review changed test hunks and linked PR commits. Record the exact test name, path, commit, setup,
input, assertion, and expected results. A strong regression test:

- exercises the vulnerable path or minimal equivalent;
- fails against the vulnerable tree for the security-relevant reason;
- passes against the fixed tree;
- includes a positive baseline and a negative/security assertion where feasible.

If execution is safe and in scope, use the repository's pinned runner and preserve logs. Never
claim execution from source inspection alone. Build failures, flaky tests, missing fixtures, or
environment drift must remain distinct from a security-regression failure.

## Pitfalls

- Merge commits can produce misleading parent diffs.
- Squash merges can disconnect PR commit SHAs from the default branch.
- Backports may have different SHAs but equivalent patches.
- Release tags may be mutable or signed/annotated; record peeled commit IDs.
- Generated snapshots may obscure the human-authored assertion.
- A changed test may cover compatibility, not security.
- A test in a later commit may still be linked evidence, but not `changed_tests` in the fix diff.
- Large release-to-release diffs require isolating the minimal fix before deriving a motif.

When no defensible regression test exists, set `changed_tests: null` with the search scope and
reason. Do not synthesize a test and present it as maintainer evidence.
