from pathlib import Path
import json
import re

ROOT = Path(".")

MANIFEST_PATH = (
    ROOT
    / "state"
    / "takeover"
    / "manifest.json"
)


def load_manifest():

    if not MANIFEST_PATH.exists():

        raise FileNotFoundError(
            f"Manifest not found: {MANIFEST_PATH}"
        )

    return json.loads(
        MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )


def normalize(text):

    return re.sub(
        r"[^a-z0-9א-ת ]+",
        " ",
        str(text).lower()
    )


def classify_mission(description):

    text = normalize(description)

    categories = {

        "sync": [
            "sync",
            "synchron",
            "סנכרון",
            "סנכרן",
        ],

        "health": [
            "health",
            "diagnostic",
            "diagnostics",
            "בדיקה",
            "בריאות",
            "אבחון",
        ],

        "token": [
            "token",
            "wallet",
            "blockchain",
            "ton",
            "טוקן",
            "ארנק",
        ],

        "doctor": [
            "doctor",
            "medical",
            "healthcare",
            "רופא",
            "רפואה",
        ],

        "system": [
            "system",
            "kernel",
            "os",
            "runtime",
            "מערכת",
            "קרנל",
        ],
    }

    scores = {}

    for category, keywords in categories.items():

        score = 0

        for keyword in keywords:

            if keyword in text:

                score += 1

        scores[category] = score

    best_category = "general"
    best_score = 0

    for category, score in scores.items():

        if score > best_score:

            best_category = category
            best_score = score

    return {
        "category": best_category,
        "score": best_score,
        "scores": scores,
    }


def agent_capability(agent):

    name = normalize(
        agent.get("name", "")
    )

    role = normalize(
        agent.get("role", "")
    )

    combined = (
        name
        + " "
        + role
    )

    capabilities = []

    if (
        "sync" in combined
        or "סנכרון" in combined
    ):

        capabilities.append(
            "sync"
        )

    if (
        "token" in combined
        or "blockchain" in combined
        or "wallet" in combined
    ):

        capabilities.append(
            "token"
        )

    if (
        "doctor" in combined
        or "medical" in combined
        or "רופא" in combined
    ):

        capabilities.append(
            "doctor"
        )

    if (
        "system" in combined
        or "guard" in combined
        or "kernel" in combined
    ):

        capabilities.append(
            "system"
        )

    return capabilities


def score_agent(
    agent,
    mission_category
):

    score = 0

    state = agent.get(
        "state",
        "unknown"
    )

    if state == "active":

        score += 1

    if state == "idle":

        score += 2

    capabilities = agent_capability(
        agent
    )

    if mission_category in capabilities:

        score += 10

    if mission_category == "general":

        score += 1

    return score


def main():

    print("=" * 80)
    print("              SLH RESPONSIBILITY MAP")
    print("                 READ-ONLY MODE")
    print("=" * 80)

    manifest = load_manifest()

    agents = manifest.get(
        "agents",
        {}
    ).get(
        "items",
        []
    )

    missions = manifest.get(
        "missions",
        {}
    ).get(
        "open_items",
        []
    )

    if not missions:

        print()
        print(
            "✅ NO OPEN MISSIONS"
        )

        return 0

    for mission in missions:

        description = mission.get(
            "description",
            ""
        )

        classification = classify_mission(
            description
        )

        category = classification.get(
            "category"
        )

        print()
        print("-" * 80)

        print(
            "MISSION:",
            f"#{mission.get('id')}"
        )

        print(
            "DESCRIPTION:",
            description
        )

        print(
            "CATEGORY:",
            category
        )

        print(
            "CLASSIFICATION SCORE:",
            classification.get(
                "score"
            )
        )

        print()
        print(
            "CANDIDATE AGENTS:"
        )

        candidates = []

        for agent in agents:

            score = score_agent(
                agent,
                category
            )

            capabilities = agent_capability(
                agent
            )

            candidates.append(
                (
                    score,
                    agent,
                    capabilities
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        for score, agent, capabilities in candidates:

            print(
                f"  [{agent.get('id')}] "
                f"{agent.get('name')} | "
                f"state={agent.get('state')} | "
                f"score={score} | "
                f"capabilities={capabilities}"
            )

        best = candidates[0]

        print()
        print(
            "RECOMMENDED AGENT:",
            best[1].get(
                "name"
            )
        )

        print(
            "RECOMMENDATION SCORE:",
            best[0]
        )

        print()
        print(
            "ACTION:"
        )

        print(
            "⚪ NO AUTOMATIC ASSIGNMENT"
        )

        print(
            "⚪ NO DATABASE WRITE"
        )

        print(
            "⚪ HUMAN / CONTROLLED APPROVAL REQUIRED"
        )

    print()
    print("=" * 80)
    print("RESPONSIBILITY ANALYSIS COMPLETE")
    print("NO FILES MODIFIED")
    print("NO DATABASE RECORDS MODIFIED")
    print("NO AGENTS MODIFIED")
    print("NO MISSIONS MODIFIED")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
