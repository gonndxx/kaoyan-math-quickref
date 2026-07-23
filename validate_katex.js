"use strict";

const fs = require("fs");
const path = require("path");

const katexRoot = process.argv[2];
if (!katexRoot) {
  process.stderr.write("KaTeX package path is required.\n");
  process.exit(2);
}
const katex = require(path.resolve(katexRoot));
const cards = JSON.parse(fs.readFileSync(0, "utf8"));
const failures = [];

for (const card of cards) {
  try {
    katex.renderToString(`\\begin{aligned}${card.latex}\\end{aligned}`, {
      displayMode: true,
      throwOnError: true,
      strict: false,
      trust: false,
      output: "html",
    });
  } catch (error) {
    failures.push(`${card.id}: ${error.message}`);
  }
}

if (failures.length) {
  process.stderr.write(failures.join("\n") + "\n");
  process.exit(1);
}
process.stdout.write(`KaTeX: ${cards.length} formulas rendered successfully.\n`);
