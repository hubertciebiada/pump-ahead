namespace PumpAhead.Adapters.Web.Services;

public class RefreshService
{
    public event Func<Task>? OnRefreshRequested;

    public async Task RequestRefreshAsync()
    {
        if (OnRefreshRequested is not null)
        {
            await OnRefreshRequested.Invoke();
        }
    }
}
