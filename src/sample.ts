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
