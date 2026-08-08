/* Temporary debug: equal-height trust cards */
(function () {
  // #region agent log
  function send(hypothesisId, message, data) {
    fetch('http://127.0.0.1:7431/ingest/15b5aa1f-f97a-42c4-8de4-bc9cab7ebdc3', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Debug-Session-Id': '016b5f',
      },
      body: JSON.stringify({
        sessionId: '016b5f',
        runId: 'pre-fix',
        hypothesisId: hypothesisId,
        location: 'sfrfr-debug-trust-cards.js',
        message: message,
        data: data,
        timestamp: Date.now(),
      }),
    }).catch(function () {});
  }

  function measure() {
    var root = document.querySelector('.sfrfr-trust');
    var main = document.querySelector('.sfrfr-trust__main');
    var rules = document.querySelector('.sfrfr-trust__rules');
    if (!root || !main || !rules) {
      send('E', 'trust nodes missing', {
        hasRoot: !!root,
        hasMain: !!main,
        hasRules: !!rules,
      });
      return;
    }

    var csRoot = getComputedStyle(root);
    var csMain = getComputedStyle(main);
    var csRules = getComputedStyle(rules);
    var rRoot = root.getBoundingClientRect();
    var rMain = main.getBoundingClientRect();
    var rRules = rules.getBoundingClientRect();

    send('A', 'parent flex layout', {
      viewportW: window.innerWidth,
      display: csRoot.display,
      flexDirection: csRoot.flexDirection,
      alignItems: csRoot.alignItems,
      gap: csRoot.gap,
      rootH: Math.round(rRoot.height),
    });

    send('B', 'children align/height', {
      mainAlignSelf: csMain.alignSelf,
      rulesAlignSelf: csRules.alignSelf,
      mainHeight: csMain.height,
      rulesHeight: csRules.height,
      mainMinHeight: csMain.minHeight,
      rulesMinHeight: csRules.minHeight,
      mainFlex: csMain.flex,
      rulesFlex: csRules.flex,
    });

    send('C', 'bounding rects tops/bottoms', {
      mainTop: Math.round(rMain.top),
      rulesTop: Math.round(rRules.top),
      mainBottom: Math.round(rMain.bottom),
      rulesBottom: Math.round(rRules.bottom),
      mainH: Math.round(rMain.height),
      rulesH: Math.round(rRules.height),
      heightDiff: Math.round(Math.abs(rMain.height - rRules.height)),
      topDiff: Math.round(Math.abs(rMain.top - rRules.top)),
      bottomDiff: Math.round(Math.abs(rMain.bottom - rRules.bottom)),
      equalHeight: Math.abs(rMain.height - rRules.height) < 1,
    });

    send('D', 'padding box model', {
      mainPad: csMain.paddingTop + '/' + csMain.paddingRight + '/' + csMain.paddingBottom + '/' + csMain.paddingLeft,
      rulesPad: csRules.paddingTop + '/' + csRules.paddingRight + '/' + csRules.paddingBottom + '/' + csRules.paddingLeft,
      mainDisplay: csMain.display,
      rulesDisplay: csRules.display,
      mainBox: csMain.boxSizing,
      rulesBox: csRules.boxSizing,
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      requestAnimationFrame(measure);
    });
  } else {
    requestAnimationFrame(measure);
  }
  // #endregion
})();
