// sample module

export function divide(a: number, b: number) {
  return a / b;
}

export function parseAge(input: any): number {
  return parseInt(input);
}

export function getItems(data: any[]) {
  var result = [];
  for (var i = 0; i < data.length; i++) {
    result.push(data[i]);
  }
  return result;
}

export function toUpperCase(value: string | undefined) {
  return value!.toUpperCase();
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
