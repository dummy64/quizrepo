const express = require("express");
const fs = require("fs");
const path = require("path");
const cron = require("node-cron");
const OpenAI = require("openai");

// --- Config ---
const PORT = process.env.PORT || 3000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const QUIZ_TOPIC = process.env.QUIZ_TOPIC || "general knowledge and tech trivia";
const DATA_DIR = path.join(__dirname, "data");

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR);

let openai;
function getOpenAI() {
  if (!openai) openai = new OpenAI({ apiKey: OPENAI_API_KEY });
  return openai;
}
const app = express();
app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));

// --- Helpers ---
function todayStr() {
  return new Date().toISOString().slice(0, 10);
}

function quizPath(date) {
  return path.join(DATA_DIR, `quiz-${date}.json`);
}

function readJSON(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}

function writeJSON(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}

function getLeaderboard() {
  return readJSON(path.join(DATA_DIR, "leaderboard.json"), []);
}

function saveLeaderboard(lb) {
  writeJSON(path.join(DATA_DIR, "leaderboard.json"), lb);
}

// --- Quiz Generation ---
async function generateQuiz() {
  const date = todayStr();
  if (fs.existsSync(quizPath(date))) {
    console.log(`Quiz for ${date} already exists, skipping.`);
    return;
  }

  console.log(`Generating quiz for ${date}...`);
  const resp = await getOpenAI().chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "user",
        content: `Generate exactly 50 multiple-choice questions about: ${QUIZ_TOPIC}.
Return ONLY a JSON array of objects with keys: "text", "options" (object with keys A,B,C,D), "correct" (one of A,B,C,D).
No markdown, no explanation, just the JSON array.`,
      },
    ],
    temperature: 0.8,
    max_tokens: 16000,
  });

  const raw = resp.choices[0].message.content.trim();
  // Strip markdown fences if present
  const jsonStr = raw.replace(/^```json?\n?/, "").replace(/\n?```$/, "");
  const questions = JSON.parse(jsonStr);

  writeJSON(quizPath(date), { date, topic: QUIZ_TOPIC, questions });
  console.log(`Quiz for ${date} saved (${questions.length} questions).`);
}

// --- API Routes ---

// Get today's quiz (without correct answers)
app.get("/api/quiz", (req, res) => {
  const date = req.query.date || todayStr();
  const quiz = readJSON(quizPath(date), null);
  if (!quiz) return res.status(404).json({ error: "No quiz for this date." });

  // Strip correct answers before sending
  const questions = quiz.questions.map((q, i) => ({
    id: i,
    text: q.text,
    options: q.options,
  }));
  res.json({ date: quiz.date, topic: quiz.topic, total: questions.length, questions });
});

// Submit answers
app.post("/api/submit", (req, res) => {
  const { name, email, answers, date, timeTaken } = req.body;
  if (!name || !email || !answers) {
    return res.status(400).json({ error: "name, email, and answers are required." });
  }

  const quizDate = date || todayStr();
  const quiz = readJSON(quizPath(quizDate), null);
  if (!quiz) return res.status(404).json({ error: "No quiz for this date." });

  // Score
  let correct = 0;
  quiz.questions.forEach((q, i) => {
    if (answers[String(i)] === q.correct) correct++;
  });
  const total = quiz.questions.length;
  const score = Math.round((correct / total) * 100);

  // Save to results file
  const resultsPath = path.join(DATA_DIR, `results-${quizDate}.json`);
  const results = readJSON(resultsPath, []);

  // Prevent duplicate submissions (same email, same date)
  if (results.find((r) => r.email === email)) {
    return res.status(409).json({ error: "You already submitted for this quiz." });
  }

  const entry = { name, email, correct, total, score, timeTaken, submittedAt: new Date().toISOString() };
  results.push(entry);
  writeJSON(resultsPath, results);

  // Update leaderboard (cumulative)
  const lb = getLeaderboard();
  const existing = lb.find((e) => e.email === email);
  if (existing) {
    existing.totalCorrect += correct;
    existing.totalQuestions += total;
    existing.quizzesTaken += 1;
    existing.name = name;
    existing.avgScore = Math.round((existing.totalCorrect / existing.totalQuestions) * 100);
    existing.lastPlayed = quizDate;
  } else {
    lb.push({
      name,
      email,
      totalCorrect: correct,
      totalQuestions: total,
      quizzesTaken: 1,
      avgScore: score,
      lastPlayed: quizDate,
    });
  }
  lb.sort((a, b) => b.avgScore - a.avgScore || b.totalCorrect - a.totalCorrect);
  saveLeaderboard(lb);

  res.json({ correct, total, score, timeTaken });
});

// Get leaderboard
app.get("/api/leaderboard", (req, res) => {
  res.json(getLeaderboard());
});

// Get daily results
app.get("/api/results/:date", (req, res) => {
  const results = readJSON(path.join(DATA_DIR, `results-${req.params.date}.json`), []);
  res.json(results);
});

// --- Cron: generate quiz daily at 8 AM ---
cron.schedule("0 8 * * *", () => {
  generateQuiz().catch((err) => console.error("Cron quiz generation failed:", err));
});

// --- Start ---
app.listen(PORT, () => {
  console.log(`Quiz server running on http://localhost:${PORT}`);
  // Generate today's quiz on startup if missing
  generateQuiz().catch((err) => console.error("Startup quiz generation failed:", err));
});
