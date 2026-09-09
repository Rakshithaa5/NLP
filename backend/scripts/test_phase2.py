"""
Quick smoke test for all Phase 2 services.
Run from project root with: python -m backend.scripts.test_phase2
"""
import sys
import os

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

SAMPLE_TRANSCRIPT = """
Good morning everyone. Let's get started with the sprint review.
Alice, can you please update the documentation by end of day Friday?
We decided to move the release date to next Monday.
John needs to schedule a meeting with the design team this week.
How many resources do we have for the next sprint?
The current system handles about ten thousand requests per minute.
We discussed the pros and cons of switching to a microservices architecture.
Sarah will handle the deployment to the staging environment.
We agreed to use PostgreSQL as our primary database going forward.
Is the API documentation up to date with the latest changes?
The team has grown to twelve engineers across three time zones.
We debated whether to rewrite the authentication module using OAuth 2.0.
Bob, can you send the invoice to the finance team by Thursday?
The decision was made to prioritize the mobile app over the web dashboard.
We brainstormed ideas for improving the user onboarding experience.
"""


def test_preprocessing():
    print("\n=== preprocessing ===")
    from backend.services.preprocessing import preprocess
    result = preprocess(SAMPLE_TRANSCRIPT)
    print(f"  Sentences : {len(result['sentences'])}")
    print(f"  Tokens    : {sum(len(t) for t in result['tokens'])} total")
    print(f"  Sample    : {result['sentences'][:2]}")
    assert len(result["sentences"]) > 0, "No sentences returned"
    assert "doc" in result, "Doc missing from result"
    print("  ✓ PASSED")
    return result


def test_ner(doc):
    print("\n=== NER ===")
    from backend.services.ner import extract_entities
    entities = extract_entities(doc)
    for e in entities:
        print(f"  [{e['label']}] {e['text']}")
    assert isinstance(entities, list), "NER should return a list"
    print(f"  ✓ PASSED — {len(entities)} entities")
    return entities


def test_classification(sentences):
    print("\n=== Classification ===")
    from backend.services.classification import classify_sentences
    results = classify_sentences(sentences)
    for r in results:
        print(f"  [{r['label']:<14}] ({r['confidence']:.2f}) {r['sentence'][:70]}")
    assert len(results) == len(sentences), "Result count mismatch"
    print(f"  ✓ PASSED — {len(results)} sentences classified")
    return results


def test_topics(sentences):
    print("\n=== Topics ===")
    from backend.services.topics import extract_topics
    result = extract_topics(sentences, n_topics=3)
    print(f"  Keywords : {result['keywords'][:10]}")
    for t in result["topics"]:
        print(f"  Topic {t['id']} (w={t['weight']:.4f}): {t['terms']}")
    assert "keywords" in result and "topics" in result, "Missing keys"
    print(f"  ✓ PASSED — {len(result['keywords'])} keywords, {len(result['topics'])} topics")


if __name__ == "__main__":
    print("Phase 2 smoke test starting …")
    prep = test_preprocessing()
    test_ner(prep["doc"])
    test_classification(prep["sentences"])
    test_topics(prep["sentences"])
    print("\n✅ All Phase 2 services passed smoke test.")
