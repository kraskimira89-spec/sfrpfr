import { ThemeProvider } from '@gravity-ui/uikit';
import { useTrackerPluginContext } from '@weavix/tracker-plugin-sdk-react';

const App = () => {
    const { theme } = useTrackerPluginContext<'navigation'>();

    return <ThemeProvider theme={theme}>Yout plugin code here</ThemeProvider>;
};

export default App;
