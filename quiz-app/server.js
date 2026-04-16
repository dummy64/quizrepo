const express = require("express");
const fs = require("fs");
const path = require("path");
const cron = require("node-cron");
const OpenAI = require("openai");

const PORT = process.env.PORT || 3000;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
const QUIZ_TOPIC = process.env.QUIZ_TOPIC || "general knowledge and tech trivia";
const QUESTIONS_PER_USER = 5;
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

function todayStr() { return new Date().toISOString().slice(0, 10); }
function quizPath(date) { return path.join(DATA_DIR, `quiz-${date}.json`); }
function sessionsPath(date) { return path.join(DATA_DIR, `sessions-${date}.json`); }
function resultsPath(date) { return path.join(DATA_DIR, `results-${date}.json`); }

function readJSON(filePath, fallback) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, "utf-8"));
}
function writeJSON(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2));
}
function getLeaderboard() { return readJSON(path.join(DATA_DIR, "leaderboard.json"), []); }
function saveLeaderboard(lb) { writeJSON(path.join(DATA_DIR, "leaderboard.json"), lb); }

function pickRandom(arr, n) {
  const shuffled = [...arr].sort(() => Math.random() - 0.5);
  return shuffled.slice(0, n);
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
    messages: [{
      role: "user",
      content: `Generate exactly 50 multiple-choice questions about: ${QUIZ_TOPIC}.
Return ONLY a JSON array of objects with keys: "text", "options" (object with keys A,B,C,D), "correct" (one of A,B,C,D).
No markdown, no explanation, just the JSON array.`,
    }],
    temperature: 0.8,
    max_tokens: 16000,
  });
  const raw = resp.choices[0].message.content.trim();
  const jsonStr = raw.replace(/^```json?\n?/, "").replace(/\n?```$/, "");
  const questions = JSON.parse(jsonStr);
  writeJSON(quizPath(date), { date, topic: QUIZ_TOPIC, questions });
  console.log(`Quiz for ${date} saved (${questions.length} questions).`);
}

// --- API Routes ---

// Start a quiz session — assigns 5 random questions, records start time
app.post("/api/start", (req, res) => {
  const { name, email } = req.body;
  if (!name || !email) return res.status(400).json({ error: "Name and email are required." });

  const date = todayStr();
  const quiz = readJSON(quizPath(date), null);
  if (!quiz) return res.status(404).json({ error: "No quiz available today. Check back soon!" });

  // Already submitted today?
  const results = readJSON(resultsPath(date), []);
  if (results.find(r => r.email === email)) {
    return res.status(409).json({ error: "already_submitted", message: "You've already taken today's quiz!" });
  }

  // Check for existing session (resume)
  const sessions = readJSON(sessionsPath(date), {});
  if (sessions[email]) {
    const s = sessions[email];
    const questions = s.questionIds.map(id => ({
      id, text: quiz.questions[id].text, options: quiz.questions[id].options,
    }));
    return res.json({ date, topic: quiz.topic, total: questions.length, questions, startedAt: s.startedAt, resumed: true });
  }

  // New session — pick 5 random questions
  const picked = pickRandom(quiz.questions.map((_, i) => i), QUESTIONS_PER_USER);
  const startedAt = new Date().toISOString();
  sessions[email] = { name, questionIds: picked, startedAt };
  writeJSON(sessionsPath(date), sessions);

  const questions = picked.map(id => ({
    id, text: quiz.questions[id].text, options: quiz.questions[id].options,
  }));
  res.json({ date, topic: quiz.topic, total: questions.length, questions, startedAt, resumed: false });
});

// Submit answers — time calculated server-side
app.post("/api/submit", (req, res) => {
  const { email, answers, date: reqDate } = req.body;
  if (!email || !answers) return res.status(400).json({ error: "Email and answers are required." });

  const date = reqDate || todayStr();
  const quiz = readJSON(quizPath(date), null);
  if (!quiz) return res.status(404).json({ error: "No quiz for this date." });

  // Check duplicate
  const results = readJSON(resultsPath(date), []);
  if (results.find(r => r.email === email)) {
    return res.status(409).json({ error: "already_submitted", message: "You've already taken today's quiz!" });
  }

  // Get session for start time
  const sessions = readJSON(sessionsPath(date), {});
  const session = sessions[email];
  if (!session) return res.status(400).json({ error: "No active session. Please start the quiz first." });

  // Calculate time server-side
  const timeTaken = Math.floor((Date.now() - new Date(session.startedAt).getTime()) / 1000);

  // Score only the assigned questions
  let correct = 0;
  session.questionIds.forEach(id => {
    if (answers[String(id)] === quiz.questions[id].correct) correct++;
  });
  const total = session.questionIds.length;
  const score = Math.round((correct / total) * 100);

  const entry = { name: session.name, email, correct, total, score, timeTaken, submittedAt: new Date().toISOString() };
  results.push(entry);
  writeJSON(resultsPath(date), results);

  // Clean up session
  delete sessions[email];
  writeJSON(sessionsPath(date), sessions);

  // Update leaderboard
  const lb = getLeaderboard();
  const existing = lb.find(e => e.email === email);
  if (existing) {
    existing.totalCorrect += correct;
    existing.totalQuestions += total;
    existing.quizzesTaken += 1;
    existing.name = session.name;
    existing.avgScore = Math.round((existing.totalCorrect / existing.totalQuestions) * 100);
    existing.lastPlayed = date;
  } else {
    lb.push({ name: session.name, email, totalCorrect: correct, totalQuestions: total, quizzesTaken: 1, avgScore: score, lastPlayed: date });
  }
  lb.sort((a, b) => b.avgScore - a.avgScore || b.totalCorrect - a.totalCorrect);
  saveLeaderboard(lb);

  res.json({ correct, total, score, timeTaken });
});

app.get("/api/leaderboard", (req, res) => res.json(getLeaderboard()));

app.get("/api/results/:date", (req, res) => {
  res.json(readJSON(resultsPath(req.params.date), []));
});

// --- Cron: daily at 8 AM ---
cron.schedule("0 8 * * *", () => {
  generateQuiz().catch(err => console.error("Cron quiz generation failed:", err));
});

app.listen(PORT, () => {
  console.log(`Quiz server running on http://localhost:${PORT}`);
  generateQuiz().catch(err => console.error("Startup quiz generation failed:", err));
});
