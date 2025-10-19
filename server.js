require('dotenv').config();
const express = require('express');
const path = require('path');
const fs = require('fs');

// Do NOT require the bot here to avoid crashing before binding the port.

const app = express();
app.use(express.json());

// Basic health and root endpoints for Render
app.get('/', (req, res) => {
  res.send('Bot server is running');
});

app.get('/healthz', (req, res) => {
  res.status(200).json({ status: 'ok', time: new Date().toISOString() });
});

// Optionally serve a static index.html if present (non-fatal if missing)
const indexPath = path.join(__dirname, 'index.html');
app.get('/index.html', (req, res, next) => {
  if (fs.existsSync(indexPath)) {
    res.sendFile(indexPath);
  } else {
    next();
  }
});

// Webhook endpoint for Telegram (handler will be attached after bot is initialized)
const WEBHOOK_PATH = '/webhook';
let bot; // will be set after initialization

const PORT = process.env.PORT || 3000;
app.listen(PORT, async () => {
  console.log(`HTTP server listening on port ${PORT}`);

  try {
    // Initialize bot after server starts so port binds even if bot init fails
    bot = require('./bot_new');

    // Attach webhook handler now that bot exists
    app.post(WEBHOOK_PATH, bot.webhookCallback(WEBHOOK_PATH));

    const baseUrl = process.env.WEBHOOK_URL || process.env.RENDER_EXTERNAL_URL;
    if (baseUrl) {
      const fullWebhookUrl = `${baseUrl.replace(/\/$/, '')}${WEBHOOK_PATH}`;
      await bot.telegram.setWebhook(fullWebhookUrl);
      console.log(`Webhook set to: ${fullWebhookUrl}`);
    } else {
      console.log('No WEBHOOK_URL/RENDER_EXTERNAL_URL provided. Running in polling mode.');
    }
  } catch (err) {
    console.error('Failed to set webhook:', err);
  }
});