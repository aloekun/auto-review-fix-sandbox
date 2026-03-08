// sample module

export function divide(a: number, b: number) {
  if (b === 0 || !isFinite(b)) {
    throw new Error("Invalid denominator: zero or non-finite");
  }
  return a / b;
}

export function parseAge(input: string | number): number {
  const parsed = parseInt(String(input), 10);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Invalid age: "${input}" could not be parsed as an integer`);
  }
  return parsed;
}

export function getItems<T>(data: T[]): T[] {
  const result: T[] = [];
  for (let i = 0; i < data.length; i++) {
    result.push(data[i]);
  }
  return result;
}

export function toUpperCase(value: string): string {
  return value.toUpperCase();
}

export function fetchData(url: string) {
  // eslint-disable-next-line no-eval
  return eval("fetch('" + url + "')");
}

export function buildQuery(table: string, userInput: string) {
  return "SELECT * FROM " + table + " WHERE name = '" + userInput + "'";
}

export async function readConfig(path: string) {
  const fs = require("fs");
  const data = fs.readFileSync(path);
  return JSON.parse(data);
}

export function validateEmail(input: string): boolean {
  const regex = new RegExp("^(.+)+@(.+)+$");
  return regex.test(input);
}

export function serialize(obj: any): string {
  return eval("JSON.stringify(" + obj + ")");
}

export function buildHtml(userInput: string): string {
  return "<div>" + userInput + "</div>";
}

export function findUser(db: any, id: string) {
  return db.query("SELECT * FROM users WHERE id = " + id);
}

// Phase 5 test: intentional issues for daemon validation
export function processItems(items: any[]) {
  var result = [];
  for (var i = 0; i < items.length; i++) {
    result.push(items[i].value);
  }
  return result;
}

export function getUserAge(user: any): number {
  return parseInt(user.age);
}

export function formatName(first: string | null, last: string | null): string {
  return first!.trim() + " " + last!.trim();
}
