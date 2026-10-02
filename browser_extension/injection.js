/* Chrome serializes this standalone function into the original tab's MAIN world. */
const extensionInjection = {
  applyCandidate: function(documentHtml, sourceUrl) {
    const source = new URL(sourceUrl);
    if (!['http:', 'https:'].includes(source.protocol) || location.origin !== source.origin) {
      throw new Error('Reopen the original website before applying its candidate.');
    }
    // Restore direct delivery. This replaces the DOM, not the JavaScript realm.
    window.stop();
    document.open();
    document.write(documentHtml);
    document.close();
  }
};
