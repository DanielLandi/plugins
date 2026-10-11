/**
 * How a sung word is matched everywhere (scene lookups, a web page's kept words): case and punctuation ignored,
 * accents on Latin letters ignored ('Ônibus,' = 'onibus'), every script kept, and outside Latin the marks that
 * change a word are kept (Devanagari vowel signs, Japanese dakuten).
 */
export const normWord = (s: string) =>
  s
    .normalize('NFKD')
    .replace(/(\p{Script=Latin})\p{M}+/gu, '$1')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\p{M}]/gu, '')
    .normalize('NFC');
